"""Inspección heurística del HTML/DOM recibido (sin ejecutar JavaScript).

Todo lo que reporta son **indicios**: un contenedor vacío sugiere renderizado en cliente, pero
no lo prueba; la ausencia de botones "cargar más" en el HTML no descarta que se creen con JS.
Solo se analizan enlaces presentes en la página; no se prueban rutas ni endpoints no enlazados.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from web_extractor.inspectors.base import InspectionOutput
from web_extractor.models.results import FetchedDocument, Finding

_ROOT_IDS = ("root", "app", "__next", "__nuxt", "main-app", "svelte")
_FRAMEWORK_MARKERS = {
    "React": re.compile(r"data-reactroot|react-dom|__REACT_DEVTOOLS", re.I),
    "Next.js": re.compile(r"__NEXT_DATA__|/_next/static", re.I),
    "Nuxt/Vue": re.compile(r"window\.__NUXT__|data-v-[0-9a-f]{6,}|vue(?:\.min)?\.js", re.I),
    "Angular": re.compile(r"ng-version=|ng-app", re.I),
    "Svelte": re.compile(r"svelte-[a-z0-9]{5,}", re.I),
}
_NEXT_TEXT = re.compile(r"^(siguiente|next|más\s*›|›|»|>|older|próxima|sig\.?)$", re.I)
_LOAD_MORE = re.compile(r"(cargar|ver|mostrar)\s+más|load\s+more|show\s+more|see\s+more", re.I)
_INFINITE = re.compile(r"infinite[-_ ]?scroll|IntersectionObserver|data-infinite|scrollHeight", re.I)
_DATA_EXT = re.compile(r"\.(csv|json|xlsx?|xml|geojson|parquet|zip)(\?|$)", re.I)
_API_DOC = re.compile(r"\b(api|openapi|swagger|developers?|desarrolladores|datos abiertos|open data)\b", re.I)
_PAGE_PARAM = re.compile(r"[?&](page|p|pagina|offset|start)=\d+", re.I)
_HEADINGS = ["h1", "h2", "h3", "h4", "h5", "h6"]
_PAGE_NUMBER = re.compile(r"(?<=[?&])(page|p|pg|pagina|página)=\d+", re.I)
_GRAPHQL = re.compile(r"/graphql\b|__APOLLO_STATE__|apollo-client|urql|relay-runtime|\bgql`", re.I)
_TIMED = re.compile(r"countdown|cuenta regresiva|new EventSource\(|new WebSocket\(", re.I)
_DATE_PARAM = re.compile(r"[?&](fecha|date|dia|day|year|anio|año)=[^&#]+", re.I)
_CHROME = ("nav", "header", "footer")
_CHROME_CLASS = re.compile(r"(^|[-_])(nav|navbar|menu|footer|header|breadcrumb|identifier|social|skip)([-_]|$)", re.I)


def _css_for(tag: Tag) -> str:
    classes = [c for c in tag.get("class", []) if re.fullmatch(r"[A-Za-z_][\w-]*", c)]
    return tag.name + "".join(f".{c}" for c in classes[:3])


_BLOCKS = ("div", "section", "article", "ul", "ol", "li", "table", "form", "header", "footer", "nav")


def _is_value_tag(tag: Tag) -> bool:
    """Elemento que contiene un valor (texto propio), no un contenedor de maquetación."""
    return bool(tag.get_text(strip=True)) and tag.find(_BLOCKS) is None


def _is_site_chrome(tag: Tag) -> bool:
    """Menús, cabeceras y pies de página: se repiten en cada página pero no son registros de datos."""
    for node in [tag, *tag.parents]:
        if getattr(node, "name", None) in _CHROME:
            return True
        if any(_CHROME_CLASS.search(c) for c in node.get("class", []) if isinstance(node, Tag)):
            return True
    return False


class HtmlInspector:
    name = "html"

    def applies_to(self, doc: FetchedDocument) -> bool:
        return doc.is_html

    def inspect(self, doc: FetchedDocument) -> InspectionOutput:
        out = InspectionOutput()
        soup = BeautifulSoup(doc.text, "html.parser")
        f = out.findings

        title = soup.title.get_text(strip=True) if soup.title else ""
        body = soup.body or soup
        scripts = soup.find_all("script")
        script_chars = sum(len(s.get_text()) for s in scripts)
        noscript = soup.find("noscript")
        noscript_text = noscript.get_text(" ", strip=True) if noscript else ""
        for tag in body.find_all(["script", "style", "noscript", "template"]):
            tag.extract()
        visible_text = " ".join(body.get_text(" ", strip=True).split())
        elements = len(body.find_all(True))
        f.append(Finding("html.summary", "dom", f"Título: '{title[:80]}'; {elements} elementos; "
                         f"{len(visible_text):,} caracteres de texto visible; {len(scripts)} scripts",
                         visible_text[:160]))

        self._render_hints(doc, soup, visible_text, scripts, script_chars, noscript_text, elements, f)
        self._tables(soup, out)
        self._repeated(body, out)
        self._pagination(doc, soup, out)
        self._on_demand(doc, soup, f)
        self._structured(doc, soup, out)
        self._forms(soup, f)
        self._interaction(soup, f)
        self._timing(doc, soup, f)
        meta = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
        if meta and meta.get("content"):
            f.append(Finding("html.meta_robots", "política", "Meta robots declarado", meta["content"]))
        return out

    def _render_hints(self, doc, soup, visible_text, scripts, script_chars, noscript_text, elements, f) -> None:
        raw = doc.text
        for root_id in _ROOT_IDS:
            root = soup.find(id=root_id)
            if root is not None and len(root.get_text(strip=True)) < 30:
                f.append(Finding("js.empty_root", "renderizado",
                                 f"Contenedor #{root_id} vacío en el HTML inicial: contenido probablemente generado con JS",
                                 str(root)[:120], {"browser": 0.45, "static_html": -0.3}))
                break
        for name, pattern in _FRAMEWORK_MARKERS.items():
            if m := pattern.search(raw):
                f.append(Finding("js.framework", "renderizado", f"Marcador de framework: {name}",
                                 m.group(0)[:80], {"browser": 0.1}))
        if re.search(r"javascript", noscript_text, re.I):
            f.append(Finding("js.noscript", "renderizado", "Aviso <noscript> que pide habilitar JavaScript",
                             noscript_text[:120], {"browser": 0.15}))
        if scripts and len(visible_text) < 200 and script_chars > len(visible_text):
            f.append(Finding("js.low_text", "renderizado",
                             "Poco texto visible frente al volumen de scripts",
                             f"texto={len(visible_text)} scripts={script_chars}", {"browser": 0.2, "static_html": -0.15}))
        elif elements < 80 and len(scripts) >= 3:
            f.append(Finding("js.thin_dom", "renderizado",
                             "HTML inicial casi vacío con varios scripts: el contenido probablemente se carga con "
                             "JavaScript/AJAX. Confírmelo con el render del navegador",
                             f"{elements} elementos, {len(scripts)} scripts", {"browser": 0.35, "static_html": -0.2}))
        elif len(visible_text) >= 300:
            f.append(Finding("html.text_present", "dom", "Hay texto sustancial en el HTML inicial",
                             f"{len(visible_text)} caracteres", {"static_html": 0.2}))
        if re.search(r"fetch\(|XMLHttpRequest|axios\.", raw):
            f.append(Finding("js.async_load", "renderizado",
                             "Los scripts cargan datos de forma asíncrona (fetch/XHR). No se infieren ni se "
                             "llaman sus endpoints: no están documentados", "", {"browser": 0.1}))
        if m := _GRAPHQL.search(raw):
            f.append(Finding("api.graphql", "api",
                             "Indicios de una API GraphQL usada por la página. No se consulta: solo se usaría con "
                             "documentación pública del propietario", m.group(0)[:80], {"browser": 0.05}))

    def _tables(self, soup, out: InspectionOutput) -> None:
        tables = []
        for i, table in enumerate(soup.find_all("table")):
            headers = [" ".join(th.get_text(" ", strip=True).split()) for th in table.find_all("th")]
            rows = len(table.find_all("tr"))
            selector = f"table#{table['id']}" if table.get("id") else (_css_for(table) if table.get("class") else f"table:nth-of-type({i + 1})")
            tables.append({"selector": selector, "headers": headers[:20], "rows": rows})
        if tables:
            with_headers = [t for t in tables if t["headers"] and t["rows"] > 1]
            out.findings.append(Finding("html.tables", "tabla", f"{len(tables)} tabla(s) HTML; {len(with_headers)} con encabezados",
                                        json.dumps(tables[:3], ensure_ascii=False),
                                        {"static_html": 0.25} if with_headers else {}))
            out.candidates["tables"] = tables

    def _repeated(self, body, out: InspectionOutput) -> None:
        groups: dict[tuple, list[Tag]] = defaultdict(list)
        for tag in body.find_all(True):
            if (tag.get("class") and tag.parent is not None
                    and tag.name not in ("span", "a", "i", "b", "strong", "img", "option", "td", "th", "tr")
                    and not _is_site_chrome(tag)):
                groups[(id(tag.parent), _css_for(tag))].append(tag)
        candidates = []
        for (_, selector), tags in groups.items():
            if len(tags) >= 3:
                avg_text = sum(len(t.get_text(strip=True)) for t in tags) / len(tags)
                if avg_text >= 10:
                    sample = tags[0]
                    children = Counter(_css_for(c) for c in sample.find_all(True)
                                       if c.get("class") and _is_value_tag(c))
                    for heading in sample.find_all(_HEADINGS):
                        if not heading.get("class"):
                            children[heading.name] += 1
                    candidates.append({"selector": selector, "count": len(tags), "avg_text": round(avg_text),
                                       "child_selectors": [c for c, _ in children.most_common(8)],
                                       "has_link": sample.find("a", href=True) is not None})
        candidates.sort(key=lambda c: (c["count"], c["avg_text"]), reverse=True)
        if candidates:
            top = candidates[0]
            out.findings.append(Finding("html.repeated", "estructura",
                                        f"Estructura repetida candidata a registro: '{top['selector']}' ×{top['count']}",
                                        ", ".join(top["child_selectors"][:5]), {"static_html": 0.15}))
            out.candidates["record_selectors"] = candidates[:5]

    def _pagination(self, doc, soup, out: InspectionOutput) -> None:
        f = out.findings
        evidence = []
        suggestion: dict | None = None
        rel_next = soup.find(["a", "link"], rel=lambda v: v and "next" in v)
        if rel_next is not None:
            evidence.append(f"rel=next -> {rel_next.get('href')}")
            if rel_next.name == "a":
                suggestion = {"mode": "next_link", "next_selector": 'a[rel~="next"]'}
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            is_next = bool(_NEXT_TEXT.match(text)) or a.get("aria-label", "").lower() in ("next", "siguiente")
            if is_next:
                evidence.append(f"enlace '{text or a.get('aria-label')}' -> {a['href']}")
                if suggestion is None and a.get("class"):
                    suggestion = {"mode": "next_link", "next_selector": _css_for(a)}
            elif _PAGE_PARAM.search(a["href"]):
                evidence.append(f"parámetro de página -> {a['href']}")
            if suggestion is None and (is_next or _PAGE_PARAM.search(a["href"])):
                href = urljoin(doc.final_url, a["href"])
                template, count = _PAGE_NUMBER.subn(lambda m: f"{m.group(1)}={{page}}", href, count=1)
                if count and urlsplit(href).path == urlsplit(doc.final_url).path:
                    suggestion = {"mode": "url_template", "url_template": template}
        if suggestion:
            out.candidates["pagination"] = suggestion
        if soup.select("nav.pagination, .pagination, .pager, [aria-label*=pagina], [aria-label*=pagination]"):
            evidence.append("contenedor de paginación")
        if evidence:
            f.append(Finding("html.pagination", "paginación", "Indicios de paginación por enlaces",
                             "; ".join(dict.fromkeys(evidence))[:300], {"static_html": 0.1}))

    def _on_demand(self, doc, soup, f) -> None:
        for el in soup.find_all(["button", "a"]):
            text = el.get_text(" ", strip=True)
            if _LOAD_MORE.search(text):
                has_href = el.name == "a" and el.get("href") and not el["href"].startswith(("#", "javascript"))
                weights = {"static_html": 0.1} if has_href else {"browser": 0.3, "static_html": -0.1}
                f.append(Finding("html.load_more", "bajo demanda",
                                 f"Control 'cargar más' ({el.name}{' con enlace' if has_href else ' sin enlace: requiere clic'})",
                                 str(el)[:160], weights))
                break
        if m := _INFINITE.search(doc.text):
            f.append(Finding("html.infinite_scroll", "bajo demanda", "Indicios de scroll infinito / carga al desplazarse",
                             m.group(0), {"browser": 0.3}))
        if soup.find(attrs={"loading": "lazy"}):
            f.append(Finding("html.lazy", "bajo demanda", "Recursos con loading=lazy (imágenes diferidas)", ""))

    def _structured(self, doc, soup, out: InspectionOutput) -> None:
        f = out.findings
        files, docs = [], []
        host = urlsplit(doc.final_url).netloc
        # Los enlaces dentro de los registros son contenido (p. ej. una charla "datos abiertos"), no navegación.
        record_links: set[int] = set()
        for cand in out.candidates.get("record_selectors", [])[:1]:
            record_links = {id(a) for el in soup.select(cand["selector"]) for a in el.find_all("a")}
        for a in soup.find_all("a", href=True):
            href = urljoin(doc.final_url, a["href"])
            text_hint = id(a) not in record_links and _API_DOC.search(a.get_text(" ", strip=True))
            if text_hint or re.search(r"openapi|swagger|/docs?/|api-docs", href, re.I):
                docs.append({"url": href, "text": a.get_text(strip=True)[:60]})
            elif _DATA_EXT.search(urlsplit(href).path + ("?" if "?" in href else "")):
                files.append({"url": href, "text": a.get_text(strip=True)[:60], "same_host": urlsplit(href).netloc == host})
        for link in soup.find_all("link", attrs={"type": re.compile("json|csv|rss|atom|xml")}):
            files.append({"url": urljoin(doc.final_url, link.get("href", "")), "text": link.get("type"), "same_host": True})
        if files:
            f.append(Finding("html.data_files", "estructurado",
                             f"{len(files)} enlace(s) a archivos estructurados descargables",
                             ", ".join(x["url"] for x in files[:4]), {"structured_file": 0.5}))
            out.candidates["data_files"] = files[:10]
        if docs:
            f.append(Finding("html.api_docs", "api", "Enlaces que parecen documentación de API/datos abiertos "
                             "(verificar manualmente que sea pública y autorizada)",
                             ", ".join(x["url"] for x in docs[:4]), {"api": 0.35}))
            out.candidates["api_docs"] = docs[:10]
        ld = soup.find_all("script", type="application/ld+json")
        if ld:
            f.append(Finding("html.json_ld", "estructurado", f"{len(ld)} bloque(s) JSON-LD (schema.org) embebidos",
                             ld[0].get_text()[:120], {"static_html": 0.05}))

    def _interaction(self, soup, f) -> None:
        controls = soup.select("[onclick], [aria-expanded], [role=tab], details, [data-toggle], [data-bs-toggle], "
                               "select[onchange]")
        if controls:
            sample = ", ".join(dict.fromkeys(_css_for(c) for c in controls[:6]))
            f.append(Finding("dom.interaction", "interacción",
                             f"{len(controls)} elemento(s) que muestran contenido al interactuar (pestañas, "
                             "desplegables, clics): ese contenido puede no estar en el HTML inicial", sample,
                             {"browser": 0.1}))

    def _timing(self, doc, soup, f) -> None:
        evidence = []
        if refresh := soup.find("meta", attrs={"http-equiv": re.compile("^refresh$", re.I)}):
            evidence.append(f"meta refresh {refresh.get('content', '')}")
        if m := _TIMED.search(doc.text):
            evidence.append(m.group(0))
        if soup.find("input", attrs={"type": re.compile("^(date|datetime-local|month)$", re.I)}):
            evidence.append("selector de fecha")
        dated = [a["href"] for a in soup.find_all("a", href=True) if _DATE_PARAM.search(a["href"])]
        if len(dated) >= 3:
            evidence.append(f"{len(dated)} enlaces parametrizados por fecha, p. ej. {dated[0][:80]}")
        if evidence:
            for header in ("last-modified", "expires"):
                if value := next((v for k, v in doc.headers.items() if k.lower() == header), None):
                    evidence.append(f"{header}: {value}")
            f.append(Finding("time.dependent", "tiempo",
                             "El contenido depende del momento de la consulta (actualización, caducidad o fecha). "
                             "Cada registro guarda su fecha de adquisición; repetir la extracción puede dar otros datos",
                             "; ".join(evidence)[:240]))

    def _forms(self, soup, f) -> None:
        if soup.find("input", attrs={"type": re.compile("^password$", re.I)}):
            f.append(Finding("html.login_form", "acceso",
                             "Formulario con contraseña: el contenido puede requerir autenticación. Solo continuar "
                             "con autorización expresa y credenciales propias", ""))
        if soup.find("form", attrs={"role": "search"}) or soup.find("input", attrs={"type": "search"}):
            f.append(Finding("html.search_form", "dom", "Formulario de búsqueda presente", ""))
