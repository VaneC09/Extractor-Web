"""Contenido renderizado con JavaScript mediante Selenium (Chrome headless).

Acciones acotadas por ``limits``: navegación (cuenta como solicitud), clics en "cargar más"
(``max_clicks``), scroll (``max_scrolls``) y paginación por enlace (``max_pages``). Cada acción se
registra, se respeta la pausa entre acciones, se comprueba cancelación y se buscan barreras en
el DOM resultante. El navegador se cierra siempre en ``close()``.

No se usan opciones para ocultar la automatización ni se modifica la huella del navegador.
Limitación conocida: Selenium no expone el código HTTP de la navegación ni filtra los
subrecursos que cargue la página; el presupuesto cuenta navegaciones y acciones, no subrecursos.
"""

from __future__ import annotations

from typing import Iterator

from web_extractor.core.barriers import detect_barrier
from web_extractor.core.errors import BarrierDetected, BrowserUnavailable, LimitReached
from web_extractor.extractors.base import AcquisitionContext, BaseAdapter
from web_extractor.extractors.static_html import find_next_link
from web_extractor.models.results import FetchedDocument
from web_extractor.utils.timeutils import utc_now_iso


class SeleniumSession:
    """Envoltura mínima de WebDriver con las políticas de la herramienta."""

    def __init__(self, ctx: AcquisitionContext) -> None:
        self.ctx = ctx
        self.driver = None

    def start(self) -> None:
        try:
            from selenium import webdriver
            from selenium.common.exceptions import WebDriverException
        except ImportError as exc:
            raise BrowserUnavailable("Selenium no está instalado (pip install selenium)") from exc
        browser = self.ctx.cfg.extraction.browser
        options = webdriver.ChromeOptions()
        if browser.headless:
            options.add_argument("--headless=new")
        # Necesario para ejecutar Chrome dentro de contenedores/VM sin espacio de nombres de usuario.
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,900")
        options.add_argument(f"--user-agent={self.ctx.cfg.user_agent}")
        try:
            self.driver = webdriver.Chrome(options=options)
        except WebDriverException as exc:
            raise BrowserUnavailable(f"No se pudo iniciar Chrome/ChromeDriver: {exc.msg}") from None
        self.driver.set_page_load_timeout(browser.page_load_timeout_seconds)
        self.ctx.actions.record("browser_start", "", "Chrome headless" if browser.headless else "Chrome")

    def close(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
                self.ctx.actions.record("browser_close", "", "navegador cerrado")
            finally:
                self.driver = None

    def navigate(self, url: str, purpose: str) -> None:
        from selenium.common.exceptions import TimeoutException, WebDriverException

        ctx = self.ctx
        ctx.budget.check()
        ctx.client.ensure_allowed(url)
        ctx.budget.consume_request()
        ctx.rate.wait_turn()
        try:
            self.driver.get(url)
        except TimeoutException:
            ctx.actions.record("browser_get", url, f"{purpose}: timeout de carga", "error")
            raise
        except WebDriverException as exc:
            ctx.actions.record("browser_get", url, f"{purpose}: {exc.msg}", "error")
            raise
        ctx.actions.record("browser_get", url, purpose)
        self.check_barrier()
        ctx.client.ensure_allowed(self.driver.current_url)

    def check_barrier(self) -> None:
        barrier = detect_barrier(None, {}, self.driver.page_source)
        if barrier:
            barrier.url = self.driver.current_url
            self.ctx.actions.record("barrier_detected", self.driver.current_url, barrier.kind, "stop")
            raise BarrierDetected(barrier)

    def wait_for(self, selector: str | None, timeout: float) -> bool:
        if not selector:
            return True
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as ec
        from selenium.webdriver.support.ui import WebDriverWait

        try:
            WebDriverWait(self.driver, timeout).until(ec.presence_of_element_located((By.CSS_SELECTOR, selector)))
            return True
        except TimeoutException:
            self.ctx.actions.record("wait_timeout", self.driver.current_url, f"no apareció '{selector}'", "warning")
            return False

    def count(self, selector: str | None) -> int:
        from selenium.webdriver.common.by import By

        return len(self.driver.find_elements(By.CSS_SELECTOR, selector)) if selector else 0

    def wait_increase(self, selector: str | None, before: int, timeout: float, height_before: int | None = None) -> bool:
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.support.ui import WebDriverWait

        def grew(driver) -> bool:
            if selector and self.count(selector) > before:
                return True
            if height_before is not None:
                return driver.execute_script("return document.body.scrollHeight") > height_before
            return False

        try:
            WebDriverWait(self.driver, timeout, poll_frequency=0.2).until(grew)
            return True
        except TimeoutException:
            return False

    def snapshot(self, page_index: int) -> FetchedDocument:
        return FetchedDocument(
            url=self.driver.current_url,
            final_url=self.driver.current_url,
            status=200,
            content_type="text/html; rendered",
            text=self.driver.page_source,
            fetched_at=utc_now_iso(),
            via="browser",
            page_index=page_index,
        )


class SeleniumBrowserAdapter(BaseAdapter):
    name = "browser"

    def __init__(self, ctx: AcquisitionContext) -> None:
        super().__init__(ctx)
        self.session = SeleniumSession(ctx)

    def close(self) -> None:
        self.session.close()

    def _load_more(self) -> None:
        from selenium.common.exceptions import WebDriverException
        from selenium.webdriver.common.by import By

        ctx, s = self.ctx, self.session
        browser = ctx.cfg.extraction.browser
        record_selector = ctx.cfg.extraction.record_selector
        while True:
            if record_selector and s.count(record_selector) >= ctx.budget.records_remaining:
                ctx.actions.record("load_more_skip", "", "ya hay registros suficientes para max_records")
                return
            buttons = s.driver.find_elements(By.CSS_SELECTOR, browser.load_more_selector)
            button = next((b for b in buttons if b.is_displayed() and b.is_enabled()), None)
            if button is None:
                ctx.actions.record("load_more_end", s.driver.current_url, "no hay más botón activo")
                return
            if ctx.budget.clicks >= ctx.budget.limits.max_clicks:
                ctx.actions.record("limit", s.driver.current_url, "max_clicks alcanzado", "stop")
                ctx.notes.append("Se alcanzó max_clicks con el botón aún activo: puede haber más contenido sin cargar")
            ctx.budget.consume_click()
            ctx.budget.consume_request()
            ctx.rate.wait_turn()
            before = s.count(record_selector)
            try:
                s.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                button.click()
            except WebDriverException as exc:
                ctx.actions.record("click", s.driver.current_url, f"fallo al hacer clic: {exc.msg}", "error")
                return
            ctx.actions.record("click", s.driver.current_url, f"'{browser.load_more_selector}'")
            if not s.wait_increase(record_selector, before, browser.wait_timeout_seconds):
                ctx.actions.record("load_more_noop", s.driver.current_url, "el clic no añadió registros", "warning")
                return
            s.check_barrier()

    def _scroll(self) -> None:
        ctx, s = self.ctx, self.session
        browser = ctx.cfg.extraction.browser
        record_selector = ctx.cfg.extraction.record_selector
        while True:
            if record_selector and s.count(record_selector) >= ctx.budget.records_remaining:
                ctx.actions.record("scroll_skip", "", "ya hay registros suficientes para max_records")
                return
            if ctx.budget.scrolls >= ctx.budget.limits.max_scrolls:
                ctx.actions.record("limit", s.driver.current_url, "max_scrolls alcanzado", "stop")
                ctx.notes.append("Se alcanzó max_scrolls: puede haber más contenido sin cargar")
            ctx.budget.consume_scroll()
            ctx.budget.consume_request()
            ctx.rate.wait_turn()
            before = s.count(record_selector)
            height = s.driver.execute_script("return document.body.scrollHeight")
            s.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            ctx.actions.record("scroll", s.driver.current_url, f"altura previa {height}px")
            ctx.cancel.wait(browser.scroll_pause_seconds)
            if not s.wait_increase(record_selector, before, browser.wait_timeout_seconds, height):
                ctx.actions.record("scroll_end", s.driver.current_url, "no se cargó más contenido")
                return
            s.check_barrier()

    def iter_documents(self) -> Iterator[FetchedDocument]:
        ctx = self.ctx
        extraction = ctx.cfg.extraction
        browser = extraction.browser
        self.session.start()
        url: str | None = ctx.cfg.target_url
        visited: set[str] = set()
        index = 0
        while url:
            ctx.budget.consume_page()
            self.session.navigate(url, f"página {index + 1}")
            visited.add(url)
            self.session.wait_for(browser.wait_selector or extraction.record_selector, browser.wait_timeout_seconds)
            pending_limit: LimitReached | None = None
            try:
                if browser.load_more_selector:
                    self._load_more()
                if browser.infinite_scroll:
                    self._scroll()
            except LimitReached as exc:
                pending_limit = exc
            doc = self.session.snapshot(index)
            yield doc
            if pending_limit is not None:
                raise pending_limit
            url = None
            if extraction.pagination.mode == "next_link":
                url = find_next_link(doc.text, doc.final_url, extraction.pagination.next_selector or "")
                if url in visited:
                    ctx.actions.record("pagination_loop", url or "", "enlace ya visitado", "stop")
                    url = None
            index += 1
