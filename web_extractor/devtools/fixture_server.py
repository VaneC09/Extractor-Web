"""Servidor HTTP local con escenarios controlados (todos los datos son ficticios).

Rutas estáticas: archivos de ``fixtures/site``.
Rutas dinámicas:
- ``/robots.txt``: prohíbe ``/privado/``.
- ``/static/catalogo?page=N``: catálogo HTML paginado (3 páginas, con un duplicado y precios sucios).
- ``/api/v1/products?page=N``: API JSON documentada en ``/api/docs.html``.
- ``/auth/login`` y ``/auth/privado``: autenticación por formulario con credenciales ficticias
  (``FIXTURE_LOGIN_USER`` / ``FIXTURE_LOGIN_PASSWORD``, con valores por defecto de prueba).
  ``/auth/informes.csv`` es el mismo contenido como archivo descargable tras iniciar sesión y
  ``/auth/panel`` lo dibuja con JavaScript (para el navegador con sesión).
- ``/api/v1/privado``: API documentada que exige ``Authorization: Bearer`` (``FIXTURE_API_TOKEN``).
- ``/barrier/limite`` (429), ``/barrier/prohibido`` (403), ``/barrier/inestable`` (502 una vez).
- ``/privado/...``: existe, pero robots.txt lo prohíbe; sirve para comprobar que no se solicita.
- ``/nuevo/agenda?pagina=N``: sitio "no visto" sin configuración de ejemplo (ISO-8859-1, otra estructura).
- ``/nuevo/redirige`` (301 a otro host: ``localhost``) y ``/nuevo/desafio`` (403 con desafío anti-bot).

Registra cada solicitud en ``hits`` para que las pruebas verifiquen los topes.
"""

from __future__ import annotations

import html
import json
import mimetypes
import os
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

SITE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "site"
DEFAULT_USER = "usuario_demo"
DEFAULT_PASSWORD = "clave-ficticia-solo-pruebas"
DEFAULT_API_TOKEN = "token-ficticio-solo-pruebas"

PRODUCTS = [
    {"sku": "SKU-001", "name": "Cuaderno reciclado A5", "price": "$45.50 MXN", "stock": "Disponible", "updated": "2025-01-10"},
    {"sku": "SKU-002", "name": "Lápiz de grafito HB", "price": "$8.00 MXN", "stock": "Disponible", "updated": "2025-01-11"},
    {"sku": "SKU-003", "name": "Mochila escolar  azul", "price": "$1,299.00 MXN", "stock": "Agotado", "updated": "2025-01-12"},
    {"sku": "SKU-004", "name": "Calculadora científica", "price": "$389.90 MXN", "stock": "Disponible", "updated": "2025-01-12"},
    {"sku": "SKU-005", "name": "Juego de geometría", "price": "$62.00 MXN", "stock": "Disponible", "updated": "2025-01-13"},
    {"sku": "SKU-006", "name": "Marcadores pastel (12)", "price": "Consultar", "stock": "Disponible", "updated": "2025-01-14"},
    {"sku": "SKU-007", "name": "Carpeta de argollas", "price": "$95.00 MXN", "stock": "Agotado", "updated": "2025-01-15"},
    {"sku": "SKU-008", "name": "Regla de 30 cm", "price": "$15.00 MXN", "stock": "Disponible", "updated": "2025-01-15"},
    {"sku": "SKU-009", "name": "Pegamento en barra", "price": "$22.50 MXN", "stock": "Disponible", "updated": "2025-01-16"},
    {"sku": "", "name": "Producto sin código", "price": "$10.00 MXN", "stock": "Disponible", "updated": "2025-01-16"},
]
CATALOG_PAGES = [PRODUCTS[0:4], PRODUCTS[4:8], PRODUCTS[8:10] + [PRODUCTS[3]]]

API_ITEMS = [
    {"id": i, "name": f"Producto API {i}", "price": {"amount": round(10 + i * 3.25, 2), "currency": "MXN"},
     "category": ["papelería", "arte", "oficina"][i % 3], "active": i % 4 != 0}
    for i in range(1, 10)
]
API_PAGE_SIZE = 4

EVENTS = [
    ("Taller de encuadernación", "12/03/2025", "Biblioteca Ñuñoa", "Cupo: 25"),
    ("Charla: datos abiertos", "14/03/2025", "Auditorio José Martí", "Cupo: 120"),
    ("Club de lectura juvenil", "15/03/2025", "Sala Gabriela Mistral", "Cupo: 18"),
    ("Exposición de cartografía", "18/03/2025", "Galería Pública", "Entrada libre"),
    ("Taller de fotografía", "20/03/2025", "Biblioteca Ñuñoa", "Cupo: 15"),
    ("Concierto de cámara", "22/03/2025", "Auditorio José Martí", "Cupo: 200"),
    ("Curso de catalogación", "25/03/2025", "Sala Gabriela Mistral", "Cupo: 30"),
]
EVENT_PAGES = [EVENTS[0:4], EVENTS[4:7]]


def agenda_page(page: int) -> bytes:
    """Sitio "no visto": otra estructura, ISO-8859-1 declarado solo en <meta> y paginación ?pagina=N."""
    cards = "\n".join(
        f"""<div class="evento">
      <h3><a href="/nuevo/evento/{(page - 1) * 4 + i + 1}">{html.escape(title)}</a></h3>
      <p class="fecha">{when}</p><p class="lugar">{html.escape(place)}</p><span class="cupo">{html.escape(seats)}</span>
    </div>"""
        for i, (title, when, place, seats) in enumerate(EVENT_PAGES[page - 1])
    )
    nxt = f'<a href="/nuevo/agenda?pagina={page + 1}">Siguiente »</a>' if page < len(EVENT_PAGES) else ""
    body = f"""<html><head><meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
<title>Agenda cultural (ficticia)</title></head><body>
<div id="cabecera"><h1>Agenda cultural del municipio</h1><p>Actividades ficticias de demostración.</p></div>
<div class="listado">{cards}</div>
<div class="paginador"><span>Página {page} de {len(EVENT_PAGES)}</span> {nxt}</div>
</body></html>"""
    return body.encode("iso-8859-1")


def catalog_page(page: int) -> str:
    items = CATALOG_PAGES[page - 1]
    cards = "\n".join(
        f"""<article class="product" data-sku="{html.escape(p['sku'])}">
      <h2 class="product-name">{html.escape(p['name'])}</h2>
      <span class="price">{html.escape(p['price'])}</span>
      <span class="stock">{html.escape(p['stock'])}</span>
      <time class="updated" datetime="{p['updated']}">{p['updated']}</time>
      <a class="detail" href="/static/producto/{html.escape(p['sku'] or 'sin-codigo')}">Ver detalle</a>
    </article>"""
        for p in items
    )
    prev_link = f'<a rel="prev" href="/static/catalogo?page={page - 1}">Anterior</a>' if page > 1 else ""
    next_link = (f'<a class="next" rel="next" href="/static/catalogo?page={page + 1}">Siguiente</a>'
                 if page < len(CATALOG_PAGES) else "")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Catálogo de papelería (ficticio) — página {page}</title></head>
<body><main><h1>Catálogo de papelería</h1>
<p>Productos de demostración con precios ficticios para validar extracción, limpieza y paginación
de HTML estático. Página {page} de {len(CATALOG_PAGES)}.</p>
<section class="products">{cards}</section>
<nav class="pagination">{prev_link} <span>Página {page}</span> {next_link}</nav>
</main></body></html>"""


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "FixtureServer/1.0"
    sessions: set[str] = set()

    def log_message(self, fmt: str, *args) -> None:
        if os.environ.get("FIXTURE_VERBOSE"):
            super().log_message(fmt, *args)

    def _send(self, status: int, body: str | bytes, content_type: str = "text/html; charset=utf-8",
              headers: dict[str, str] | None = None) -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _record(self) -> None:
        self.server.hits.append(f"{self.command} {self.path}")  # type: ignore[attr-defined]

    def _logged_in(self) -> bool:
        cookie = self.headers.get("Cookie", "")
        return any(part.strip().startswith("fixture_session=") and part.strip().split("=", 1)[1] in self.sessions
                   for part in cookie.split(";"))

    def do_GET(self) -> None:  # noqa: N802
        self._record()
        parts = urlsplit(self.path)
        path, query = parts.path, parse_qs(parts.query)
        page = int(query.get("page", ["1"])[0]) if query.get("page", ["1"])[0].isdigit() else 1

        if path == "/robots.txt":
            return self._send(200, "User-agent: *\nDisallow: /privado/\n", "text/plain; charset=utf-8")
        if path == "/static/catalogo":
            if 1 <= page <= len(CATALOG_PAGES):
                return self._send(200, catalog_page(page))
            return self._send(404, "<h1>No encontrado</h1>")
        if path == "/api/v1/products":
            start = (page - 1) * API_PAGE_SIZE
            chunk = API_ITEMS[start:start + API_PAGE_SIZE]
            total_pages = -(-len(API_ITEMS) // API_PAGE_SIZE)
            host = self.headers.get("Host", "127.0.0.1")
            nxt = f"http://{host}/api/v1/products?page={page + 1}" if page < total_pages else None
            body = {"data": chunk, "meta": {"page": page, "total_pages": total_pages}, "links": {"next": nxt}}
            return self._send(200, json.dumps(body, ensure_ascii=False), "application/json; charset=utf-8",
                              {"X-RateLimit-Limit": "60"})
        if path == "/auth/login":
            token = secrets.token_hex(8)
            return self._send(200, f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Acceso</title></head>
<body><h1>Acceso al área de informes (entorno de prueba)</h1>
<form method="post" action="/auth/login"><input type="hidden" name="csrf_token" value="{token}">
<label>Usuario <input name="username"></label><label>Contraseña <input type="password" name="password"></label>
<button type="submit">Entrar</button></form></body></html>""")
        if path == "/auth/privado":
            if not self._logged_in():
                return self._send(302, "", headers={"Location": "/auth/login"})
            rows = "\n".join(
                f'<tr><td>INF-{i:03d}</td><td>Informe interno de prueba {i}</td><td>{"Publicado" if i % 2 else "Borrador"}</td></tr>'
                for i in range(1, 6))
            return self._send(200, f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Informes</title></head>
<body><h1>Informes del área (ficticios)</h1><table id="informes"><thead><tr><th>Folio</th><th>Título</th><th>Estado</th></tr></thead>
<tbody>{rows}</tbody></table><a href="/auth/logout">Salir</a></body></html>""")
        if path == "/auth/panel":
            if not self._logged_in():
                return self._send(302, "", headers={"Location": "/auth/login"})
            data = json.dumps([{"folio": f"INF-{i:03d}", "titulo": f"Informe interno de prueba {i}",
                                "estado": "Publicado" if i % 2 else "Borrador"} for i in range(1, 6)], ensure_ascii=False)
            return self._send(200, f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Panel</title></head>
<body><h1>Panel del área (ficticio)</h1><div id="root"></div><a href="/auth/logout">Salir</a>
<script>
setTimeout(function () {{
  var rows = {data};
  document.getElementById("root").innerHTML = rows.map(function (r) {{
    return '<div class="informe"><span class="folio">' + r.folio + '</span><span class="titulo">' + r.titulo +
           '</span><span class="estado">' + r.estado + '</span></div>';
  }}).join("");
}}, 300);
</script></body></html>""")
        if path == "/api/v1/privado":
            token = os.environ.get("FIXTURE_API_TOKEN", DEFAULT_API_TOKEN)
            if self.headers.get("Authorization") != f"Bearer {token}":
                return self._send(401, json.dumps({"error": "token ausente o inválido"}), "application/json")
            items = [{"codigo": f"ART-{i:02d}", "descripcion": f"Artículo interno {i}", "existencias": i * 7}
                     for i in range(1, 7)]
            return self._send(200, json.dumps({"data": items}, ensure_ascii=False), "application/json; charset=utf-8")
        if path == "/auth/informes.csv":
            if not self._logged_in():
                return self._send(302, "", headers={"Location": "/auth/login"})
            rows = "\n".join(f"INF-{i:03d},Informe interno de prueba {i},{'Publicado' if i % 2 else 'Borrador'}"
                             for i in range(1, 6))
            return self._send(200, f"Folio,Título,Estado\n{rows}\n", "text/csv; charset=utf-8")
        if path == "/barrier/limite":
            return self._send(429, "<h1>Demasiadas solicitudes</h1>", headers={"Retry-After": "120"})
        if path == "/barrier/prohibido":
            return self._send(403, "<h1>Acceso denegado</h1>")
        if path == "/barrier/inestable":
            self.server.unstable_count += 1  # type: ignore[attr-defined]
            if self.server.unstable_count == 1:  # type: ignore[attr-defined]
                return self._send(502, "<h1>Bad gateway</h1>")
            return self._send(200, catalog_page(1))
        if path.startswith("/privado/"):
            return self._send(200, "<h1>Recurso que robots.txt prohíbe</h1>")
        if path == "/nuevo/agenda":
            number = query.get("pagina", ["1"])[0]
            number = int(number) if number.isdigit() else 0
            if 1 <= number <= len(EVENT_PAGES):
                return self._send(200, agenda_page(number), "text/html")
            return self._send(404, "<h1>No encontrado</h1>")
        if path == "/nuevo/redirige":
            port = self.server.server_address[1]  # type: ignore[attr-defined]
            return self._send(301, "", headers={"Location": f"http://localhost:{port}/nuevo/agenda"})
        if path == "/nuevo/desafio":
            return self._send(403, "<html><head><title>Just a moment...</title></head><body>"
                                   "<div id='cf-chl-widget'>Checking your browser before accessing.</div></body></html>")
        return self._serve_file(path)

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self) -> None:  # noqa: N802
        self._record()
        length = int(self.headers.get("Content-Length", "0") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        if urlsplit(self.path).path == "/auth/login":
            user = os.environ.get("FIXTURE_LOGIN_USER", DEFAULT_USER)
            password = os.environ.get("FIXTURE_LOGIN_PASSWORD", DEFAULT_PASSWORD)
            if form.get("username", [""])[0] == user and form.get("password", [""])[0] == password and form.get("csrf_token"):
                session = secrets.token_hex(16)
                self.sessions.add(session)
                return self._send(303, "", headers={"Location": "/auth/privado",
                                                    "Set-Cookie": f"fixture_session={session}; Path=/; HttpOnly"})
            return self._send(401, "<h1>Credenciales incorrectas</h1>")
        return self._send(405, "<h1>Método no permitido</h1>")

    def _serve_file(self, path: str) -> None:
        if path in ("", "/"):
            path = "/index.html"
        target = (SITE_DIR / path.lstrip("/")).resolve()
        if SITE_DIR.resolve() not in target.parents or not target.is_file():
            return self._send(404, "<h1>No encontrado</h1>")
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type.endswith("json"):
            content_type += "; charset=utf-8"
        return self._send(200, target.read_bytes(), content_type)


class FixtureServer:
    """Arranca el servidor en un hilo. ``port=0`` elige un puerto libre (útil en pruebas)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.httpd = ThreadingHTTPServer((host, port), FixtureHandler)
        self.httpd.hits = []  # type: ignore[attr-defined]
        self.httpd.unstable_count = 0  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    @property
    def hits(self) -> list[str]:
        return self.httpd.hits  # type: ignore[attr-defined]

    def start(self) -> "FixtureServer":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def __enter__(self) -> "FixtureServer":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
