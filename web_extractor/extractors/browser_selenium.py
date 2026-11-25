"""Contenido renderizado con JavaScript mediante Selenium (Chrome o Edge headless).

Acciones acotadas por ``limits``: navegación (cuenta como solicitud), clics en "cargar más"
(``max_clicks``), scroll (``max_scrolls``) y paginación por enlace (``max_pages``). Cada acción se
registra, se respeta la pausa entre acciones, se comprueba cancelación y se buscan barreras en
el DOM resultante. El navegador se cierra siempre en ``close()``.

Con ``auth.type=form`` autorizado, inicia sesión escribiendo en el formulario las credenciales
leídas de variables de entorno (nunca se registran), en una pantalla o en dos (usuario y después
contraseña). Si el sitio pide un código de verificación, solo continúa cuando el titular de la
cuenta lo escribe. Si el acceso se rechaza o aparece una barrera, se detiene sin reintentar.

Con ``browser.human_verification``, si aparece un CAPTCHA o desafío, el navegador se abre visible y
la herramienta espera (máx. 5 min, sin hacer solicitudes) a que **una persona** lo resuelva; nunca lo
resuelve ni lo envía a servicios externos. Si se repite más de 3 veces, se detiene.

No se usan opciones para ocultar la automatización ni se modifica la huella del navegador.
Limitación conocida: Selenium no expone el código HTTP de la navegación ni filtra los
subrecursos que cargue la página; el presupuesto cuenta navegaciones y acciones, no subrecursos.
"""

from __future__ import annotations

import time
from typing import Iterator

from web_extractor.core.auth import find_code_field, read_credentials, request_code
from web_extractor.core.barriers import detect_barrier
from web_extractor.core.errors import AuthFailed, BarrierDetected, BrowserUnavailable, LimitReached
from web_extractor.extractors.base import AcquisitionContext, BaseAdapter
from web_extractor.extractors.static_html import find_next_link
from web_extractor.models.results import FetchedDocument
from web_extractor.utils.timeutils import utc_now_iso


BROWSER_LABELS = {"chrome": "Chrome", "edge": "Edge"}
HUMAN_SOLVABLE = {"captcha", "bot_challenge"}
HUMAN_TIMEOUT_SECONDS = 300
MAX_HUMAN_VERIFICATIONS = 3
# Respuesta que el propio widget guarda cuando la persona completa la verificación (reCAPTCHA, hCaptcha, Turnstile).
_CAPTCHA_ANSWERED_JS = ("return Array.from(document.querySelectorAll('[name=g-recaptcha-response],"
                        "[name=h-captcha-response],[name=cf-turnstile-response]')).some(e => e.value)")
_BROWSER_BINARIES = {
    "chrome": ("google-chrome", "chromium", "chromium-browser", "chrome",
               r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
               r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
               r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    "edge": ("microsoft-edge", "msedge",
             r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
             r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
}


def available_browsers() -> list[str]:
    """Navegadores instalados que Selenium puede controlar, por orden de preferencia."""
    import os
    import shutil

    def present(candidate: str) -> bool:
        if "%" in candidate:
            return os.path.isfile(os.path.expandvars(candidate))
        return shutil.which(candidate) is not None

    return [name for name, candidates in _BROWSER_BINARIES.items() if any(present(c) for c in candidates)]


class SeleniumSession:
    """Envoltura mínima de WebDriver con las políticas de la herramienta."""

    def __init__(self, ctx: AcquisitionContext) -> None:
        self.ctx = ctx
        self.driver = None
        self.human_solved: set[str] = set()

    def start(self) -> None:
        try:
            from selenium import webdriver
            from selenium.common.exceptions import WebDriverException
        except ImportError as exc:
            raise BrowserUnavailable("Selenium no está instalado (pip install selenium)") from exc
        browser = self.ctx.cfg.extraction.browser
        engines = available_browsers() if browser.engine == "auto" else [browser.engine]
        if not engines:
            raise BrowserUnavailable("No se encontró Chrome ni Edge instalados")
        errors = []
        for engine in engines:
            options = webdriver.EdgeOptions() if engine == "edge" else webdriver.ChromeOptions()
            if browser.headless and not browser.human_verification:
                options.add_argument("--headless=new")
            # Necesario para ejecutar el navegador dentro de contenedores/VM sin espacio de nombres de usuario.
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1280,900")
            options.add_argument(f"--user-agent={self.ctx.cfg.user_agent}")
            try:
                self.driver = webdriver.Edge(options=options) if engine == "edge" else webdriver.Chrome(options=options)
                break
            except WebDriverException as exc:
                errors.append(f"{engine}: {exc.msg}")
        else:
            raise BrowserUnavailable("No se pudo iniciar el navegador: " + " | ".join(errors))
        self.driver.set_page_load_timeout(browser.page_load_timeout_seconds)
        label = BROWSER_LABELS[engine]
        visible = not browser.headless or browser.human_verification
        self.ctx.actions.record("browser_start", "", label if visible else f"{label} headless")

    def close(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
                self.ctx.actions.record("browser_close", "", "navegador cerrado")
            finally:
                self.driver = None

    def _submit(self, field, values: dict, gone: str) -> None:
        """Escribe ``values`` (nombre -> valor) en el formulario de ``field`` y espera a que ``gone`` desaparezca."""
        from selenium.common.exceptions import TimeoutException, WebDriverException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait

        ctx, auth = self.ctx, self.ctx.cfg.auth
        page = self.driver.current_url
        ctx.budget.check()
        ctx.budget.consume_request()
        ctx.rate.wait_turn()
        try:
            for name, value in values.items():
                element = self.driver.find_element(By.NAME, name)
                element.clear()
                element.send_keys(value)
            buttons = field.find_elements(
                By.XPATH, "./ancestor::form//*[self::button[not(@type) or @type='submit'] or self::input[@type='submit']]")
            if buttons:
                buttons[0].click()
            else:
                field.send_keys(Keys.ENTER)
            WebDriverWait(self.driver, ctx.cfg.extraction.browser.wait_timeout_seconds, poll_frequency=0.2).until(
                lambda d: d.current_url != page or not d.find_elements(By.NAME, gone)
                or bool(auth.failure_text and auth.failure_text in d.page_source))
        except TimeoutException:
            pass
        except WebDriverException as exc:
            ctx.actions.record("login", self.driver.current_url, f"fallo del navegador: {exc.msg}", "error")
            raise AuthFailed("No se pudo completar el inicio de sesión autorizado; no se reintenta.") from None

    def _wait_for(self, name: str):
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        try:
            return WebDriverWait(self.driver, self.ctx.cfg.extraction.browser.wait_timeout_seconds,
                                 poll_frequency=0.2).until(lambda d: d.find_elements(By.NAME, name))[0]
        except TimeoutException:
            return None

    def _rejected(self, name: str) -> bool:
        from selenium.webdriver.common.by import By

        failure = self.ctx.cfg.auth.failure_text
        return bool(self.driver.find_elements(By.NAME, name) or (failure and failure in self.driver.page_source))

    def login(self, auth) -> None:
        """Inicio de sesión autorizado en una o dos pantallas, con código 2FA escrito por el titular.

        Ante rechazo, CAPTCHA u otra barrera se detiene; no reintenta.
        """
        from selenium.webdriver.common.by import By

        ctx = self.ctx
        username, password = read_credentials(auth)
        self.navigate(auth.login_url, "formulario de acceso autorizado", auth_expected=True)
        user_input = self.driver.find_elements(By.NAME, auth.username_field)
        pass_input = self.driver.find_elements(By.NAME, auth.password_field)
        if not user_input and not pass_input:
            raise AuthFailed(f"No se encontró un formulario con los campos '{auth.username_field}' y "
                             f"'{auth.password_field}'")
        if pass_input:
            values = {auth.password_field: password}
            if user_input:
                values = {auth.username_field: username, **values}
            self._submit(pass_input[0], values, auth.password_field)
        else:
            self._submit(user_input[0], {auth.username_field: username}, auth.username_field)
            self.check_barrier(auth_expected=True)
            pass_field = self._wait_for(auth.password_field)
            if pass_field is None:
                ctx.actions.record("login", self.driver.current_url, "no apareció el campo de contraseña", "stop")
                raise AuthFailed("Tras enviar el usuario no apareció el campo de contraseña; no se reintenta.")
            ctx.actions.record("login", self.driver.current_url, "paso 1 de 2 aceptado: se pide la contraseña", "ok")
            self._submit(pass_field, {auth.password_field: password}, auth.password_field)
        self.check_barrier(auth_expected=True)
        code_field = find_code_field(self.driver.page_source, auth)
        if code_field:
            code = request_code(ctx.client, auth, self.driver.current_url)
            self._submit(self.driver.find_element(By.NAME, code_field), {code_field: code}, code_field)
            if self._rejected(code_field):
                ctx.actions.record("login", self.driver.current_url, "código de verificación rechazado", "stop")
                raise AuthFailed("El código de verificación fue rechazado; no se reintenta.")
            ctx.actions.record("login", self.driver.current_url, "código de verificación aceptado (valor oculto)", "ok")
        if self._rejected(auth.password_field):
            ctx.actions.record("login", self.driver.current_url, "credenciales rechazadas", "stop")
            raise AuthFailed("El inicio de sesión autorizado fue rechazado; no se reintenta.")
        ctx.client.ensure_allowed(self.driver.current_url)
        self.check_barrier()
        ctx.actions.record("login", self.driver.current_url, "sesión iniciada en el navegador", "ok")

    def navigate(self, url: str, purpose: str, *, auth_expected: bool = False) -> None:
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
        self.check_barrier(auth_expected=auth_expected)
        ctx.client.ensure_allowed(self.driver.current_url)

    def check_barrier(self, *, auth_expected: bool = False) -> None:
        barrier = detect_barrier(None, {}, self.driver.page_source, auth_expected=auth_expected)
        if barrier:
            barrier.url = self.driver.current_url
            if self._human_can_solve(barrier):
                return self._wait_for_human(barrier)
            self.ctx.actions.record("barrier_detected", self.driver.current_url, barrier.kind, "stop")
            raise BarrierDetected(barrier)

    def _human_can_solve(self, barrier) -> bool:
        return (barrier.kind in HUMAN_SOLVABLE and self.ctx.cfg.extraction.browser.human_verification
                and barrier.url not in self.human_solved)

    def _human_solved(self) -> bool:
        if detect_barrier(None, {}, self.driver.page_source, auth_expected=True) is None:
            return True
        return bool(self.driver.execute_script(_CAPTCHA_ANSWERED_JS))

    def _wait_for_human(self, barrier) -> None:
        """Pausa hasta que una persona resuelva la verificación en la ventana visible. Nunca se resuelve aquí."""
        ctx = self.ctx
        if len(self.human_solved) >= MAX_HUMAN_VERIFICATIONS:
            ctx.actions.record("barrier_detected", barrier.url, f"{barrier.kind}: se repite tras "
                               f"{MAX_HUMAN_VERIFICATIONS} verificaciones humanas", "stop")
            barrier.message += (f" (se repite tras {MAX_HUMAN_VERIFICATIONS} verificaciones humanas: el sitio "
                                "no admite este ritmo de acceso)")
            raise BarrierDetected(barrier)
        prompt = (f"{barrier.message}. Resuélvalo usted en la ventana del navegador; la extracción continúa sola "
                  f"cuando desaparezca (máximo {HUMAN_TIMEOUT_SECONDS // 60} min)")
        ctx.actions.record("human_verification", barrier.url, f"{barrier.kind}: esperando a una persona", "ok")
        notice = ctx.client.human_notice
        if notice:
            notice(prompt)
        solved = False
        try:
            with ctx.budget.pause():
                deadline = time.monotonic() + HUMAN_TIMEOUT_SECONDS
                while time.monotonic() < deadline:
                    ctx.cancel.wait(1.0)
                    if self._human_solved():
                        solved = True
                        break
        finally:
            if notice:
                notice(None)
        if not solved:
            ctx.actions.record("human_verification", barrier.url, f"{barrier.kind}: nadie lo resolvió a tiempo", "stop")
            barrier.message += f" (nadie lo resolvió en {HUMAN_TIMEOUT_SECONDS // 60} min)"
            raise BarrierDetected(barrier)
        self.human_solved.add(barrier.url)
        ctx.client.ensure_allowed(self.driver.current_url)
        ctx.actions.record("human_verification", self.driver.current_url, f"{barrier.kind}: resuelto por una persona", "ok")
        ctx.incidents.add(barrier.kind, f"{barrier.message} — resuelto por una persona en la ventana del navegador; "
                          "la herramienta no lo resolvió", barrier.url, barrier.next_step, severity="media")

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
        if ctx.cfg.auth.type == "form":
            self.session.login(ctx.cfg.auth)
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
