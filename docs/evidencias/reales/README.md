# Evidencias en sitios reales (datos abiertos)

Corridas **reales**, de bajo volumen, sobre los sitios de ejemplo del reto final. Cada carpeta contiene
la configuración efectiva, el diagnóstico (`diagnostico.md`) y, cuando hubo extracción, `report.md`,
`summary.json`, `data.csv`, `data.json`, `data.xlsx`, `profile.json` y `actions.jsonl` (bitácora de cada
solicitud). Las configuraciones de origen están en `examples/reales/`.

Dataset consolidado (solo la última corrida real de cada sitio, sin datos de fixtures):

- `dataset_reales.sqlite`: tablas `runs`, `records` (con `lineage_json`) e `incidents`. 5 corridas y 148 registros.
- `dataset_reales.xlsx`: hoja `corridas` y una hoja de datos por sitio.

Fecha de ejecución: 21/11/2026 (UTC). Los sitios cambian: repetir la corrida puede dar otros conteos, y
la detección de cambios de estructura (`profile.json`) lo informará.

## Resultados por sitio

| Config | URL | Mecanismo detectado (confianza) | Resultado | Solicitudes | Registros (válidos / con aviso) |
|---|---|---|---|---|---|
| r01 | https://www.datos.gob.mx/dataset/?page=1 | HTML estático con paginación por URL (alta) | completado_con_limites (tope de 2 páginas) | 3 | 40 (40 / 0) |
| r02 | https://api.worldbank.org/v2/country/MX/indicator/SP.POP.TOTL?format=json | API REST documentada, JSON, paginada (media) | completado_con_limites (tope de 2 páginas) | 3 | 40 (40 / 0) |
| r03 | https://api.worldbank.org/v2/country/MX;US;CA/indicator/NY.GDP.MKTP.CD | Archivo estructurado XML (media) | completado | 2 | 30 (30 / 0) |
| r04 | https://catalog.data.gov/ | Contenido cargado con JavaScript; extracción con Selenium (Edge headless) (media) | completado | 2 | 20 (19 / 1) |
| r05 | https://dof.gob.mx/index.php | HTML estático; contenido dependiente de la fecha (alta) | completado | 2 | 18 (16 / 2) |
| r06 | https://data.worldbank.org/ | — | **detenido**: `bot_challenge` (HTTP 403, desafío de Cloudflare) | 2 | — |
| r07 | https://www.inegi.org.mx/datosabiertos/ | DOM mínimo con 6 scripts: carga por JavaScript | **detenido**: `captcha` (Google reCAPTCHA en la página renderizada) | 3 | — |
| r08 | https://www.dof.gob.mx/ | — | **detenido**: `tls_error` (el certificado no es válido para `www`) | 1 | — |

Las solicitudes incluyen la lectura de `robots.txt`. Los avisos de r04 y r05 son campos opcionales
vacíos o enlaces sin fecha (p. ej. `indicadores.php`), y quedan anotados en `validation_errors`.

## Clasificación de protección y viabilidad legal

| Sitio | Protección observada | Viabilidad legal y técnica | Siguiente paso legítimo |
|---|---|---|---|
| datos.gob.mx | Ninguna en `/dataset/`; `robots.txt` con `Crawl-delay: 10` y `Disallow: /api/` | Viable para el listado HTML con pausa de 10 s. **No** se usa la API CKAN porque `robots.txt` la excluye. | — |
| api.worldbank.org | Ninguna; `robots.txt` responde 404 (sin restricciones) | Viable. API documentada en [Developer Information](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures); datos bajo licencia CC BY 4.0 (citar la fuente). | — |
| data.worldbank.org | Desafío anti-bot de Cloudflare (403) | **No viable** por el portal: no se evade. | Usar la API documentada (r02, r03). |
| catalog.data.gov | Ninguna; `Crawl-delay: 10` | Viable con navegador y pausa de 10 s. La API CKAN `package_search` respondió 404 y no se usa. | — |
| inegi.org.mx/datosabiertos | Google reCAPTCHA cargado por la página | Los [Términos de Libre Uso](https://www.inegi.org.mx/contenidos/inegi/doc/terminos_info.pdf) permiten reutilizar la información, pero el flujo automatizado se **detiene** ante el CAPTCHA (criterio conservador). | Descargar los archivos publicados por INEGI o pedir una vía autorizada. |
| dof.gob.mx | Formulario opcional de suscriptores (no bloquea el contenido); `robots.txt` excluye `/nota_detalle.php?` | Viable solo para el índice de `/index.php`; el alcance se limitó a ese prefijo. | — |
| www.dof.gob.mx | Certificado TLS emitido para otro nombre | **No viable**: no se desactiva la verificación TLS. | Usar `https://dof.gob.mx` (r05). |

## Qué se cubrió con sitios reales y qué solo con fixtures

Los mecanismos que se ejecutaron en sitios reales son: HTML estático, paginación, carga por JavaScript
con Selenium, API REST documentada, archivo XML, contenido dependiente de la fecha, desafío anti-bot,
CAPTCHA y certificado inválido. Ninguno de estos cinco sitios ofrece de forma legítima scroll infinito,
botón "cargar más", autenticación autorizada ni una tabla HTML con encabezados. Esos escenarios se
demuestran con los fixtures locales (`python -m web_extractor matrix`, 20 de 20 casos) y no se
presentan como pruebas sobre sitios reales.
