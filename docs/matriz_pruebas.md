# Matriz de pruebas y criterios de aceptación

Los **resultados observados** se generan con `python -m web_extractor matrix` y están en
[evidencias/matriz_resultados.md](evidencias/matriz_resultados.md) (18/18 casos cumplieron lo
esperado en la ejecución del 2026-11-18 UTC). Todos los escenarios usan fixtures locales con datos
ficticios servidos por `web_extractor/devtools/fixture_server.py`; **no se probó ningún sitio real**.

## Diseño de la matriz

| ID | Escenario | Mecanismo | Config | Autorización / entorno | Límite sol. | Resultado esperado | Decisión |
|---|---|---|---|---|---|---|---|
| T01 | HTML estático + paginación | Requests + BS4 | `f01` | fixture, propietario = equipo | 10 | 3 páginas, 10 registros, 1 duplicado, 1 inválido | Continuar |
| T02 | Tabla HTML | Requests + BS4 | `f02` | fixture | 4 | 5 filas, 2 advertencias | Continuar |
| T03 | Renderizado con JavaScript | Selenium | `f03` | fixture | 4 | 5 registros del DOM renderizado | Continuar |
| T04 | Botón «Cargar más» | Selenium | `f04` | fixture | 6 (2 clics) | 12 de 14, `completado_con_limites` | Continuar |
| T05 | Scroll infinito | Selenium | `f05` | fixture | 6 (2 scrolls) | 15 de 20, `completado_con_limites` | Continuar |
| T06 | API documentada + paginación | Requests (JSON) | `f06` | fixture, API documentada | 8 | 9 registros en 3 páginas | Continuar |
| T07 | Archivo CSV | Requests + Pandas | `f07` | fixture, licencia abierta ficticia | 3 | 5 registros, 1 duplicado | Continuar |
| T08 | Autenticación autorizada | Requests (sesión) | `f08` | fixture, `allow_authentication`, credenciales ficticias | 8 | 5 registros; contraseña ausente de salidas | Continuar |
| T09 | CAPTCHA | — | `f09` | fixture | 5 | `detenido_barrera`, incidencia `captcha`, sin reintentos | Detenerse |
| T10 | HTTP 429 | — | `f10` | fixture | 5 | `detenido_barrera`, `rate_limit`, 1 solicitud a la ruta | Detenerse |
| T11 | robots.txt prohíbe | — | `f11` | fixture | 3 | `detenido_politica`, ruta nunca solicitada | Detenerse |
| T12 | Cancelación | Requests + BS4 | `f01` | fixture | 10 | `cancelado` antes de la página 3 | Detenerse |
| T13 | Cambio de estructura | Requests + BS4 | `f01` alterado | fixture | 10 | Cambio `alta`, revisión humana, perfil intacto | Detenerse |
| T14 | Configuración inválida | — | `invalida_ejemplo` | — | — | Rechazo con errores por campo | Detenerse |
| T15 | Sitio real sin autorización | — | plantilla | production, sin confirmar | 5 | Bloqueo y lista de requisitos | Detenerse |
| T16 | API sin documentación | — | `f06` alterado | fixture | 8 | "No verificado / no ejecutar" | Detenerse |
| T17 | Sitio no visto (ISO-8859-1, sin YAML de ejemplo) | Requests + BS4 | plantilla + reglas sugeridas | fixture | 5 | 7 registros con acentos correctos, `completado_con_limites` por `max_pages=2` | Continuar |
| T18 | Sitio no visto que redirige a otro host | — | plantilla | fixture | 3 | Redirección no seguida, `out_of_scope` | Detenerse |

Cobertura: 4 mecanismos de adquisición distintos (HTML estático, navegador, archivo estructurado,
API), 11 configuraciones de sitio sobre el mismo motor, y todos los casos mínimos solicitados
(estático, JS, archivo/API, paginación, scroll/cargar más, tabla, autenticación, CAPTCHA/bloqueo).

Además, `python -m pytest` cubre de forma aislada: límites `max_pages`, `max_records`,
`max_requests` y `max_seconds`; archivo STOP; 403; 502 reintentado dentro del tope y fallo sin
reintentos; paginación fuera de alcance bloqueada; plantilla de URL que termina en 404; login
rechazado sin reintento; credenciales ausentes; página protegida sin autenticación configurada;
redacción de secretos; normalizadores, tipos y validadores; inspección y clasificación de cada
fixture; sugerencias; comparación de perfiles; códigos de salida de la CLI.

## Criterios de aceptación

| # | Criterio verificable | Evidencia |
|---|---|---|
| A1 | Acepta configuración válida y rechaza inválida con mensajes por campo | T14; `tests/unit/test_config.py` |
| A2 | El diagnóstico explica indicios, puntuación, confianza, requisitos e incertidumbre | `docs/evidencias/diagnostico_*.md`; `test_diagnosis_is_conservative_and_explained` |
| A3 | El usuario revisa campos y vista previa antes de extraer; sin confirmación no hay solicitudes de extracción | `run` muestra vista previa y pide `si`; `test_run_requires_confirmation_when_not_interactive`, `test_requires_confirmation` |
| A4 | Se aplican límites de páginas, registros, tiempo, solicitudes, clics y scrolls; la cancelación funciona | T04, T05, T12; `test_limits_are_enforced`, `test_stop_file_cancels` |
| A5 | Las barreras provocan parada segura e incidencia, sin evasión ni reintentos | T09, T10, T11; `test_barriers_stop_without_retries` |
| A6 | CSV/JSON/SQLite contienen datos normalizados y linaje (URL, fecha, ejecución, método, estado, transformaciones) | `examples/demo_dataset/`; `test_static_pagination_end_to_end` |
| A7 | Errores y logs sin credenciales ni secretos | T08; `test_authorized_login_without_leaking_secrets`, `TestRedaction` |
| A8 | Pruebas unitarias e integración repetibles localmente | `python -m pytest` (170 pruebas superadas el 2026-11-18 UTC) |
| A10 | Un sitio que no es de los ejemplos sigue el mismo flujo y las mismas paradas | T17, T18; `tests/integration/test_sitio_no_incluido.py`; [sitios_no_incluidos.md](sitios_no_incluidos.md) |
| A11 | La interfaz gráfica no permite solicitudes sin la autorización requerida y permite cancelar | `tests/integration/test_gui.py` |
| A9 | Entregables coherentes: código, dataset, informe, matriz, manual, guion | `README.md`, `docs/` |

## Sustitución por URLs autorizadas

Rellene una fila por sitio real **solo** cuando tenga el permiso. Copie la plantilla
`examples/plantilla_sitio_autorizado.yaml`, complete `authorization` y ejecute primero `diagnose`.

| ID real | Reemplaza a | URL autorizada | Propietario que autoriza | Referencia del permiso | Vigencia | Límite acordado (sol/min) | Campos autorizados | Resultado observado |
|---|---|---|---|---|---|---|---|---|
| R01 | T01 | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _no ejecutado_ |
| R02 | T02 | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _no ejecutado_ |
| R03 | T03/T04/T05 | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _no ejecutado_ |
| R04 | T06 | _pendiente (API con documentación pública)_ | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _no ejecutado_ |
| R05 | T07 | _pendiente (archivo con licencia)_ | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _pendiente_ | _no ejecutado_ |
