# Web Extractor Académico

Herramienta configurable de **diagnóstico y extracción web responsable**, escrita en Python 3.
No es un scraper para una página concreta: un único motor recibe una configuración YAML/JSON
(URL, autorización, alcance, límites, método y reglas de campos), inspecciona cómo se presenta la
información, recomienda un método con evidencia y nivel de confianza, extrae solo dentro de los
límites autorizados, limpia y valida los datos, conserva su linaje y genera informes.

Funciona con cuatro mecanismos de adquisición intercambiables:

| Método | Tecnología | Cuándo |
|---|---|---|
| `static_html` | Requests + BeautifulSoup | El contenido llega en el HTML inicial (listas, tablas, paginación por enlaces) |
| `browser` | Selenium + Chrome headless | El contenido se genera con JavaScript, botón «cargar más», scroll infinito |
| `structured_file` | Requests + Pandas | CSV/JSON descargable, público y autorizado |
| `api` | Requests | API **pública y documentada**; nunca se infieren endpoints |

## Límites de uso (obligatorios)

- Solo para sitios y datos con autorización y cuyo uso permitan sus términos. La herramienta **no
  puede verificar** la autorización: exige que una persona la declare en la configuración y la
  confirme antes de cada extracción. Sin ello, solo permite validar la configuración, diagnóstico
  pasivo (1–3 solicitudes) y pruebas con fixtures locales.
- No resuelve ni evade CAPTCHA, autenticación, paywalls, bloqueos, límites de tasa ni mecanismos
  anti-bot. Ante cualquiera de ellos **se detiene**, no reintenta y registra una incidencia con el
  paso legítimo siguiente. No usa proxies, suplantación ni ocultación de la automatización.
- Respeta robots.txt (RFC 9309), alcance de dominios/rutas, pausas mínimas (≥ 1 s en remoto),
  concurrencia 1 y topes de páginas, registros, solicitudes, clics, scrolls y tiempo.
- No admite campos con nombres de datos sensibles (CURP, RFC, tarjetas, contraseñas…) ni secretos
  en la configuración; las credenciales autorizadas se leen de variables de entorno y se enmascaran
  en logs e informes.

## Instalación

Requisitos: Python 3.10+ (probado con 3.12.3). Google Chrome solo para el método `browser`
(Selenium Manager descarga el ChromeDriver compatible la primera vez).

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # o requirements.txt sin pytest (incluye Streamlit para la GUI)
```

En Debian/Ubuntu, si `venv` falla por falta de `ensurepip`: `sudo apt-get install python3-venv`.

`requirements.txt` usa rangos acotados; `requirements-lock.txt` fija las versiones exactas con
las que se ejecutaron las pruebas documentadas.

## Interfaz gráfica

```bash
python -m web_extractor gui            # http://127.0.0.1:8611
```

Recorre el mismo flujo que la CLI en siete pestañas:

1. Proyecto y autorización, con la lista en vivo de lo que falta.
2. Alcance y límites.
3. Diagnóstico, con tarjetas de métodos, puntuación, confianza e indicios.
4. Campos y reglas, en una tabla editable, con «Aplicar sugerencia».
5. Vista previa, en vivo (1 página) o sobre un archivo local.
6. Extracción, con confirmación, progreso en vivo y botón **Cancelar**.
7. Resultados: calidad, incidencias, cambios de estructura, descargas e historial.

Desde la barra lateral se activa el sitio de pruebas local, se cargan los ejemplos y se
sube o descarga la configuración YAML. Sin autorización completa, los botones que harían
solicitudes quedan deshabilitados y la interfaz explica qué falta.

Para un sitio que **no** es uno de los ejemplos, escriba su URL en la pantalla inicial. Qué pasa en
cada caso (sin permiso, redirección a `www`, robots.txt, CAPTCHA, codificación…) se explica en
[docs/sitios_no_incluidos.md](docs/sitios_no_incluidos.md).

## Inicio rápido con el sitio de pruebas local

```bash
# Terminal 1: sitio de pruebas controlado (datos ficticios) en http://127.0.0.1:8765
python -m web_extractor serve-fixtures --port 8765

# Terminal 2: recorrido completo guiado
python -m web_extractor validate examples/f01_catalogo_estatico.yaml
python -m web_extractor diagnose examples/f01_catalogo_estatico.yaml
python -m web_extractor suggest  examples/f02_tabla_html.yaml --out outputs/borrador.yaml
python -m web_extractor preview  examples/f01_catalogo_estatico.yaml
python -m web_extractor run      examples/f01_catalogo_estatico.yaml   # pide confirmación escrita
```

Resultados en `outputs/<proyecto>/<run_id>/`: `data.csv`, `data.json`, `report.md`,
`summary.json`, `actions.jsonl`, `run.log`, `profile.json`, y la base acumulativa
`outputs/web_extractor.sqlite`.

Matriz de pruebas completa (arranca su propio servidor en un puerto libre):

```bash
python -m web_extractor matrix        # 18 casos; escribe docs/evidencias/matriz_resultados.md
python -m pytest                      # pruebas unitarias e integración con fixtures
```

Las pruebas con navegador se omiten automáticamente si no hay Chrome.

## Comandos

| Comando | Qué hace | Solicitudes al sitio |
|---|---|---|
| `validate CONFIG` | Valida el esquema y muestra qué falta de la autorización | 0 |
| `diagnose CONFIG [--render]` | Inspección pasiva, hallazgos, método sugerido y limitaciones | ≤ `diagnosis.max_requests` (+1 con render) |
| `suggest CONFIG [--out F]` | Diagnóstico + borrador de reglas de campos para revisar | igual que `diagnose` |
| `preview CONFIG [--from-file F]` | Vista previa de registros (1 página) o sobre un archivo local | 0 con `--from-file`, si no ≤ 2 |
| `run CONFIG [--yes]` | Flujo completo: autorización → diagnóstico → vista previa → confirmación → extracción → calidad → exportación → informe | dentro de `limits` |
| `compare-runs A B` | Compara perfiles de dos ejecuciones | 0 |
| `init --url URL --out F` | Asistente que crea una configuración con autorización pendiente | 0 |
| `serve-fixtures` | Sitio de pruebas local | — |
| `matrix` | Ejecuta la matriz de pruebas y guarda evidencias | solo fixtures locales |
| `gui [--port 8611]` | Interfaz gráfica local (Streamlit) con el mismo flujo y las mismas puertas | igual que cada paso |

Cancelación: `Ctrl+C` (parada tras la acción en curso) o crear el archivo `outputs/STOP`.
Códigos de salida: 0 ok, 1 error técnico, 2 configuración inválida, 3 falta autorización o
confirmación, 4 parada por barrera/política, 5 cancelado, 6 requiere revisión humana.

## Estructura

```
web_extractor/
  app.py              CLI con pasos guiados
  gui/                interfaz gráfica Streamlit (app.py) y extracción en segundo plano (jobs.py)
  config/             esquema Pydantic, cargador YAML/JSON y plantilla conservadora desde una URL
  core/               motor, autorización, alcance, límites, barreras, robots, cliente HTTP, autenticación
  inspectors/         inspectores de respuesta, HTML y datos estructurados + clasificador de método
  extractors/         adaptadores: static_html, browser (Selenium), structured_file, api
  selection/          aplicación de reglas de campos (CSS, columnas, rutas JSON) y sugerencias
  transforms/         normalizadores, tipos, validadores, canalización de calidad y linaje
  storage/            exportadores CSV, JSON y SQLite
  reports/            informes de diagnóstico y ejecución, perfiles y detección de cambios
  models/             dataclasses compartidas
  interface/          presentación en consola
  utils/              redacción de secretos, logging, tiempo
  devtools/           servidor de fixtures y ejecutor de la matriz
fixtures/site/        sitio de pruebas (HTML, JS, CSV, OpenAPI) con datos ficticios
examples/             una configuración por escenario + plantilla para sitio real + dataset demo
tests/                unitarias (sin red) e integración (servidor local, Selenium, CLI)
docs/                 informe técnico, plan de fases, manual, matriz, esquema, guion, evidencias
outputs/              resultados de ejecución (no versionados)
```

Cambio respecto de la estructura propuesta: el paquete `selectors/` se llama `selection/` para no
ocultar el módulo `selectors` de la biblioteca estándar; se añadieron `interface/` (separar la
interfaz de la lógica) y `devtools/` (fixtures y matriz).

## Documentación

- [Informe técnico](docs/informe_tecnico.md): arquitectura, decisiones, limitaciones, riesgos y viabilidad por escenario.
- [Plan de fases y estado](docs/plan_fases.md)
- [Manual de usuario y solución de errores](docs/manual_usuario.md)
- [Qué pasa con un sitio que no es de los ejemplos](docs/sitios_no_incluidos.md)
- [Matriz de pruebas y criterios de aceptación](docs/matriz_pruebas.md) · [resultados observados](docs/evidencias/matriz_resultados.md)
- [Esquema del dataset de demostración](docs/esquema_dataset.md) · [dataset](examples/demo_dataset/)
- [Guion de demostración (3–5 min)](docs/guion_demo.md)

## Estado

MVP funcional de las fases 1 a 4 (incluida la interfaz gráfica) y la mayor parte de la 5: ver
[plan de fases](docs/plan_fases.md).
Todas las pruebas se han ejecutado solo contra fixtures locales; **no se ha probado ningún sitio
real**. Para usar URLs reales hace falta la autorización descrita en
[docs/matriz_pruebas.md](docs/matriz_pruebas.md#sustitución-por-urls-autorizadas).
