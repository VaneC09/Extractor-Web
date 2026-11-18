# Plan de fases y estado de implementación

Cada fase indica objetivo, alcance, archivos, pruebas, demostración, definición de terminado y
estado real. "Implementado" significa que existe código y pruebas automatizadas que pasan en el
entorno de desarrollo contra fixtures locales; no implica validación en sitios reales.

## Fase 1 — Diagnóstico e inspección web

- **Objetivo:** dado un URL autorizado, explicar cómo se entrega la información y qué método parece
  viable, con evidencia, confianza y limitaciones, con un presupuesto mínimo de solicitudes.
- **Alcance:** configuración validada, alcance (protocolo, dominio, ruta, red privada), robots.txt,
  cliente HTTP con topes, detección de barreras, inspectores (respuesta, HTML, JSON/CSV),
  clasificador explicable, render opcional con Selenium para comparar.
- **Archivos:** `config/`, `core/scope.py`, `core/robots.py`, `core/barriers.py`, `core/limits.py`,
  `core/http_client.py`, `inspectors/*`, `reports/diagnosis_report.py`, `app.py diagnose`.
- **Pruebas:** `tests/unit/test_config.py`, `test_policies.py`, `test_selection_and_inspection.py`
  (inspección de fixtures sin red), `tests/integration/test_engine_http.py::test_diagnosis_*`,
  `test_browser.py::test_render_comparison_in_diagnosis`.
- **Demostración:** `python -m web_extractor diagnose examples/f03_js_renderizado.yaml --render`.
- **Terminado cuando:** acepta configuraciones válidas y rechaza inválidas; el diagnóstico usa ≤ 3
  solicitudes (+1 con render); cada recomendación lista indicios a favor/en contra; las barreras
  detienen el diagnóstico con incidencia.
- **Estado:** implementado.

## Fase 2 — Motor de extracción con varios métodos autorizados

- **Objetivo:** una interfaz común de adaptadores intercambiables que adquieran documentos dentro
  de topes explícitos, con registro de acciones, cancelación y cierre limpio.
- **Alcance:** `static_html` (paginación `next_link` y `url_template`), `browser` (espera, «cargar
  más», scroll infinito, paginación por enlace), `structured_file` (CSV/JSON), `api` (documentada,
  paginación `next_field` y `page_param`), autenticación autorizada por formulario (Requests y
  navegador) y por token documentado en un encabezado (API y archivo).
- **Archivos:** `extractors/*`, `core/auth.py`, `core/engine.py`, `core/tracing.py`.
- **Pruebas:** `tests/integration/test_engine_http.py` (límites, barreras, reintentos, robots,
  alcance, autenticación, cancelación) y `test_browser.py`.
- **Demostración:** `python -m web_extractor run examples/f04_cargar_mas.yaml`.
- **Terminado cuando:** el mismo motor ejecuta ≥ 4 mecanismos solo cambiando la configuración;
  los topes se respetan y se reflejan en el estado `completado_con_limites`; las barreras no se
  reintentan; el navegador se cierra siempre.
- **Estado:** implementado, incluida la autenticación con navegador (T19) y por token (T20).

## Fase 3 — Selección, transformación y calidad de datos

- **Objetivo:** reglas declarativas de campos, vista previa antes de extraer y canalización de
  calidad con linaje.
- **Alcance:** selectores CSS/atributos, columnas de tabla, rutas JSON, columnas CSV; normalizadores,
  patrones, tipos, validadores, deduplicación (Pandas), estados `valido/advertencia/invalido`,
  conservación del valor crudo, sugerencias automáticas y modo manual con `--from-file`.
- **Archivos:** `selection/*`, `transforms/*`, `engine.preview`, `app.py suggest/preview`.
- **Pruebas:** `tests/unit/test_transforms.py`, `test_selection_and_inspection.py`,
  `tests/integration/test_engine_http.py::test_preview_*`.
- **Demostración:** `python -m web_extractor suggest examples/f02_tabla_html.yaml` y
  `preview ... --from-file fixtures/site/static/tabla.html`.
- **Terminado cuando:** la vista previa muestra registros procesados y errores antes de confirmar;
  cada registro exportado lleva linaje y pasos aplicados por campo.
- **Estado:** implementado.

## Fase 4 — Persistencia, exportación e interfaz mínima

- **Objetivo:** salidas reutilizables y una interfaz guiada suficiente para el usuario final.
- **Alcance:** CSV, JSON, SQLite acumulativo; informe Markdown + resumen JSON; acciones JSONL; log
  redactado; perfiles por sitio y comparación; CLI guiada con confirmación escrita.
- **Archivos:** `storage/exporters.py`, `reports/run_report.py`, `reports/profiles.py`,
  `interface/console.py`, `app.py`.
- **Pruebas:** `test_engine_http.py::test_static_pagination_end_to_end`,
  `test_change_detection_requires_review`, `tests/integration/test_cli.py`.
- **Demostración:** `python -m web_extractor run examples/f01_catalogo_estatico.yaml`.
- **Terminado cuando:** los tres formatos contienen datos normalizados y linaje; los secretos no
  aparecen en ninguna salida; el cambio de estructura exige revisión humana sin tocar la línea base.
- **Estado:** implementado, incluida la interfaz gráfica local (`web_extractor/gui/`, comando
  `gui`). Usa las mismas funciones del motor y las mismas puertas de autorización que la CLI, y
  ejecuta la extracción en segundo plano con progreso en vivo y cancelación. Pruebas en
  `tests/integration/test_gui.py`.

## Fase 5 — Integración, pruebas, documentación y optimización

- **Objetivo:** evidencia reproducible, documentación coherente y endurecimiento.
- **Alcance:**
  - Matriz de 20 casos con resultados observados. T17 y T18 son un sitio «no visto» sin YAML
    de ejemplo; ver [sitios_no_incluidos.md](sitios_no_incluidos.md).
  - Manual, informe técnico y guion de demostración.
- **Archivos:** `devtools/matrix.py`, `docs/*`, `examples/demo_dataset/`.
- **Pruebas:** `python -m web_extractor matrix` y `python -m pytest`.
- **Terminado cuando:** la matriz y la suite pasan localmente y la documentación refleja el código.
- **Estado:** implementado para fixtures locales. **Pendiente:** sustituir fixtures por URLs
  autorizadas reales (requiere permisos), grabar el video de demostración, CI automatizada y
  optimizaciones opcionales (caché condicional con ETag/If-Modified-Since, exportación Excel,
  PostgreSQL/MongoDB).
