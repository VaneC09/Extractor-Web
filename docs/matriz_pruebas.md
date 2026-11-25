# Matriz de pruebas y criterios de aceptación

Los **resultados observados** se generan con `python -m web_extractor matrix` y están en
[evidencias/matriz_resultados.md](evidencias/matriz_resultados.md) (20/20 casos cumplieron lo
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
| T19 | Navegador con autenticación autorizada | Selenium | `f12` | fixture, `allow_authentication`, credenciales ficticias | 6 | 5 informes renderizados tras el login; 1 POST; contraseña ausente de salidas | Continuar |
| T20 | API documentada con token | Requests (JSON) + encabezado | `f13` | fixture, API documentada, token ficticio por variable de entorno | 3 | 6 registros; token ausente de salidas; huella en el linaje | Continuar |

Cobertura: 4 mecanismos de adquisición distintos (HTML estático, navegador, archivo estructurado,
API), 13 configuraciones de sitio sobre el mismo motor, y todos los casos mínimos solicitados
(estático, JS, archivo/API, paginación, scroll/cargar más, tabla, autenticación, CAPTCHA/bloqueo).
La autenticación autorizada se prueba con tres mecanismos: formulario con Requests (T08), formulario
con navegador (T19) y token documentado para APIs (T20).

En T20 el diagnóstico pasivo se detiene con `auth_required`. Es intencional: el diagnóstico nunca
envía credenciales ni tokens.

Además, `python -m pytest` cubre de forma aislada: límites `max_pages`, `max_records`,
`max_requests` y `max_seconds`; archivo STOP; 403; 502 reintentado dentro del tope y fallo sin
reintentos; paginación fuera de alcance bloqueada; plantilla de URL que termina en 404; login
rechazado sin reintento; credenciales ausentes; página protegida sin autenticación configurada;
login con navegador rechazado sin reintento; token ausente (sin solicitudes a la API) o
equivocado (401, una sola solicitud); el token nunca llega a robots.txt; encabezado no permitido
para HTML o navegador; redacción de secretos; normalizadores, tipos y validadores; inspección y clasificación de cada
fixture; sugerencias; comparación de perfiles; códigos de salida de la CLI.

## Criterios de aceptación

| # | Criterio verificable | Evidencia |
|---|---|---|
| A1 | Acepta configuración válida y rechaza inválida con mensajes por campo | T14; `tests/unit/test_config.py` |
| A2 | El diagnóstico explica indicios, puntuación, confianza, requisitos e incertidumbre | `docs/evidencias/diagnostico_*.md`; `test_diagnosis_is_conservative_and_explained` |
| A3 | El usuario revisa campos y vista previa antes de extraer; sin confirmación no hay solicitudes de extracción | `run` muestra vista previa y pide `si`; `test_run_requires_confirmation_when_not_interactive`, `test_requires_confirmation` |
| A4 | Se aplican límites de páginas, registros, tiempo, solicitudes, clics y scrolls; la cancelación funciona | T04, T05, T12; `test_limits_are_enforced`, `test_stop_file_cancels` |
| A5 | Las barreras provocan parada segura e incidencia, sin evasión ni reintentos | T09, T10, T11; `test_barriers_stop_without_retries` |
| A6 | CSV/JSON/Excel/SQLite contienen datos normalizados y linaje (URL, fecha, ejecución, método, estado, transformaciones, huella de configuración, versión) | `examples/demo_dataset/`; `test_static_pagination_end_to_end`, `test_every_output_carries_provenance` |
| A7 | Errores y logs sin credenciales ni secretos | T08, T19, T20; `test_authorized_login_without_leaking_secrets`, `test_api_with_token_header`, `TestRedaction` |
| A8 | Pruebas unitarias e integración repetibles localmente | `python -m pytest` (246 pruebas superadas, ninguna omitida, el 2026-11-25 UTC en Windows 11) |
| A10 | Un sitio que no es de los ejemplos sigue el mismo flujo y las mismas paradas | T17, T18; `tests/integration/test_sitio_no_incluido.py`; [sitios_no_incluidos.md](sitios_no_incluidos.md) |
| A11 | La interfaz gráfica no permite solicitudes sin la autorización requerida y permite cancelar | `tests/integration/test_gui.py` |
| A12 | La autenticación autorizada funciona igual con Requests, navegador y API con token, y se detiene sin reintentar si falla | T08, T19, T20; `tests/integration/test_rubrica.py` |
| A13 | Cada ejecución es reproducible: misma configuración ⇒ misma huella SHA-256, guardada con la versión | `test_fingerprint_changes_only_with_configuration`, `test_sqlite_created_by_previous_version_is_migrated` |
| A9 | Entregables coherentes: código, dataset, informe, matriz, manual, guion | `README.md`, `docs/` |
| A14 | Al menos 5 sitios reales y 4 mecanismos con evidencia de diagnóstico, extracción e informe de restricciones | R01–R08; [evidencias/reales](evidencias/reales/README.md) |

## Sustitución por URLs autorizadas

Para un sitio nuevo: copie `examples/plantilla_sitio_autorizado.yaml` (o use la GUI), complete
`authorization` y ejecute primero `diagnose`.

Corridas reales ejecutadas el 2026-11-21 (UTC), una vez cada una y con bajo volumen. Configuración
en `examples/reales/`; evidencia completa en [evidencias/reales](evidencias/reales/README.md).

| ID real | Equivale a | URL | Base de uso (referencia) | Pausa usada | Campos | Resultado observado |
|---|---|---|---|---|---|---|
| R01 | T01 (HTML + paginación) | https://www.datos.gob.mx/dataset/?page=1 | Datos abiertos; `robots.txt` (Crawl-delay 10, `/api/` excluida) | 10 s | título, url, institución, actualización | completado_con_limites: 40 registros, 2 páginas, 3 solicitudes |
| R02 | T06 (API documentada) | https://api.worldbank.org/v2/country/MX/indicator/SP.POP.TOTL?format=json | Documentación pública de la API; CC BY 4.0 | 2 s | país, código, año, población | completado_con_limites: 40 registros, 2 páginas, 3 solicitudes |
| R03 | T07 (archivo estructurado) | https://api.worldbank.org/v2/country/MX;US;CA/indicator/NY.GDP.MKTP.CD (XML) | Igual que R02 | 2 s | país, código, año, PIB | completado: 30 registros, 2 solicitudes |
| R04 | T03 (render JS) | https://catalog.data.gov/ | Datos abiertos; `robots.txt` (Crawl-delay 10) | 10 s | título, url, organización, actualizado, formatos | completado: 20 registros (19 válidos), Edge headless |
| R05 | Contenido dependiente del tiempo | https://dof.gob.mx/index.php | Publicación oficial; `robots.txt` (excluye `/nota_detalle.php?`) | 3 s | título, url, fecha de publicación | completado: 18 registros (16 válidos); indicio `time.dependent` |
| R06 | Barrera anti-bot (como T09/T10) | https://data.worldbank.org/ | — | — | — | detenido: `bot_challenge` (403 Cloudflare), código de salida 4 |
| R07 | T09 (CAPTCHA) | https://www.inegi.org.mx/datosabiertos/ | Términos de Libre Uso de INEGI | — | — | detenido: `captcha` (reCAPTCHA tras render), código de salida 4 |
| R08 | Certificado inválido | https://www.dof.gob.mx/ | — | — | — | detenido: `tls_error`, código de salida 4 |

No hay corrida real para «cargar más», scroll infinito, tabla HTML ni autenticación: ninguno de los
cinco sitios los ofrece de forma legítima, así que solo se demuestran con T04, T05, T02, T08, T19 y T20.
