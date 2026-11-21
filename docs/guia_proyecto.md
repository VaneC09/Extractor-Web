# Guía del proyecto: Extractor Web (Proyecto final_TAD)

Esta guía explica qué hace cada parte del proyecto, cómo ejecutarlo paso a paso en Windows y en qué
parte del código o de la documentación se cumple cada requisito del RETO FINAL.

Repositorio: https://github.com/VaneC09/Extractor-Web

## 1. Qué es el proyecto

Es una herramienta para **diagnosticar y extraer datos de sitios web de forma responsable**. No está
hecha para un solo sitio: un mismo motor recibe una configuración (URL, autorización, límites,
método y campos) y sirve para cualquier URL nueva sin tocar el código.

El flujo de trabajo siempre es el mismo:

1. **Autorización:** la persona declara quién autoriza, para qué se usarán los datos y que revisó los
   términos del sitio. Sin eso, la herramienta no extrae nada.
2. **Diagnóstico:** con muy pocas solicitudes (1 a 3), detecta cómo entrega los datos el sitio (HTML,
   JavaScript, API, archivo) y si hay barreras (CAPTCHA, bloqueos, robots.txt).
3. **Recomendación:** propone un método con evidencia y un nivel de confianza (alta, media o baja).
4. **Campos:** sugiere qué campos extraer; la persona los revisa o los escribe a mano.
5. **Vista previa:** muestra los primeros registros antes de extraer.
6. **Extracción:** recorre páginas dentro de los límites, con pausas y opción de cancelar.
7. **Limpieza y validación:** normaliza, convierte tipos, valida y elimina duplicados.
8. **Exportación:** CSV, JSON, Excel y SQLite, con el linaje de cada registro.
9. **Informes:** reporte de la ejecución, incidencias y detección de cambios en el sitio.

Ante un CAPTCHA, un bloqueo, un certificado inválido o una prohibición, **se detiene**, no reintenta y
registra una incidencia con el siguiente paso legítimo.

## 2. Cómo ejecutarlo (Windows, paso a paso)

### 2.1 Requisitos

- Windows 10 u 11.
- Python 3.12 (probado con 3.12.10).
- Microsoft Edge (viene con Windows) o Google Chrome, solo para el método con navegador.
- Conexión a internet para los sitios reales y para que Selenium descargue el driver la primera vez.

### 2.2 Descargar el proyecto

Opción A, con git:

```powershell
cd $HOME\Downloads
git clone https://github.com/VaneC09/Extractor-Web.git
cd Extractor-Web
```

Opción B, sin git: en GitHub pulse **Code → Download ZIP**, descomprima el archivo y abra PowerShell
dentro de la carpeta.

### 2.3 Crear el entorno e instalar dependencias

```powershell
py install 3.12                              # solo si "py -3.12" responde "No runtime installed"
py -3.12 -m venv .venv                       # crea el entorno virtual
Set-ExecutionPolicy -Scope Process Bypass    # permite activar el entorno en esta ventana
.\.venv\Scripts\Activate.ps1                 # activa el entorno: aparece (.venv) al inicio
pip install -r requirements-dev.txt          # instala dependencias y pytest
```

Cada vez que abra una ventana nueva de PowerShell, repita solo `Set-ExecutionPolicy ...` y
`.\.venv\Scripts\Activate.ps1`.

### 2.4 Abrir la interfaz gráfica (forma recomendada)

```powershell
python -m web_extractor gui
```

Se abre el navegador en http://127.0.0.1:8611. Para una URL nueva:

1. Escriba la URL en la pantalla inicial (por ejemplo `https://www.datos.gob.mx/dataset/`).
2. En **1 · Proyecto y autorización**, llene quién autoriza, la finalidad y la referencia del permiso
   (por ejemplo la página de licencia o el `robots.txt`). Marque que revisó los términos y la
   confirmación.
3. En **2 · Alcance y límites**, revise el máximo de páginas, registros y la pausa entre solicitudes.
4. En **3 · Diagnóstico**, pulse **Ejecutar diagnóstico**. Verá el método recomendado, la confianza
   y la evidencia. Pulse **Aplicar sugerencia a «Campos y reglas»**.
5. En **4 · Campos y reglas**, ajuste los campos en la tabla si hace falta.
6. En **5 · Vista previa**, pulse **Vista previa en vivo** para ver los primeros registros.
7. En **6 · Extracción**, marque la confirmación y pulse **Iniciar extracción**. Puede cancelar en
   cualquier momento.
8. En **7 · Resultados**, revise la calidad y las incidencias, y descargue CSV, JSON, Excel o el informe.

### 2.5 Usar la línea de comandos (CLI)

Con los ejemplos de sitios reales:

```powershell
python -m web_extractor validate examples\reales\r02_worldbank_api_json.yaml        # valida la configuración
python -m web_extractor diagnose --yes examples\reales\r01_datos_gob_mx_catalogo.yaml  # diagnóstico
python -m web_extractor run examples\reales\r02_worldbank_api_json.yaml             # pide escribir "si"
python -m web_extractor diagnose --yes examples\reales\r07_inegi_js_captcha.yaml    # se detiene: CAPTCHA
```

Con el sitio de pruebas local (datos ficticios, sin internet):

```powershell
python -m web_extractor serve-fixtures --port 8765     # ventana 1: deja corriendo el sitio de pruebas
python -m web_extractor run examples\f01_catalogo_estatico.yaml   # ventana 2
```

Comandos disponibles:

| Comando | Qué hace |
|---|---|
| `validate CONFIG` | Revisa la configuración y dice qué falta de la autorización (0 solicitudes) |
| `diagnose CONFIG [--render] [--yes]` | Diagnóstico y método recomendado; `--render` compara con el navegador |
| `suggest CONFIG [--out F]` | Diagnóstico y borrador de reglas de campos |
| `preview CONFIG [--from-file F]` | Vista previa en vivo (1 página) o sobre un archivo guardado |
| `run CONFIG [--yes]` | Flujo completo hasta exportar e informar |
| `compare-runs A B` | Compara los perfiles de dos ejecuciones |
| `init --url URL --out F` | Crea una configuración nueva para una URL |
| `gui` | Interfaz gráfica |
| `serve-fixtures` | Sitio de pruebas local |
| `matrix` | Ejecuta los 20 casos de prueba con el sitio local |

Códigos de salida: 0 correcto, 1 error técnico, 2 configuración inválida, 3 falta autorización,
4 parada por barrera o política, 5 cancelado, 6 requiere revisión humana.

### 2.6 Dónde quedan los resultados

Cada ejecución crea `outputs\<proyecto>\<run_id>\` con:

| Archivo | Contenido |
|---|---|
| `data.csv`, `data.json`, `data.xlsx` | Los datos con sus columnas de linaje |
| `report.md` | Informe legible de la ejecución |
| `summary.json` | Resumen: estado, límites usados, calidad, incidencias |
| `actions.jsonl` | Bitácora de cada solicitud, clic o scroll |
| `profile.json` | Perfil del sitio para detectar cambios en la próxima ejecución |
| `config_efectiva.json` | Configuración exacta usada (sin secretos) |

Además, `outputs\web_extractor.sqlite` acumula todas las ejecuciones.

### 2.7 Ejecutar las pruebas

```powershell
python -m pytest                    # 207 pruebas unitarias y de integración
python -m web_extractor matrix      # 20 escenarios con el sitio de pruebas local
```

## 3. Estructura del proyecto

```
web_extractor/        código fuente (el motor y sus módulos)
examples/             configuraciones de ejemplo
  reales/             sitios reales: datos.gob.mx, Banco Mundial, data.gov, DOF, INEGI
fixtures/site/        sitio de pruebas local con datos ficticios
tests/                pruebas unitarias e integración
docs/                 informe técnico, manual, matriz de pruebas, evidencias, esta guía
outputs/              resultados de cada ejecución (no se sube a git)
```

## 4. Módulos y métodos importantes

### 4.1 Punto de entrada: `web_extractor/app.py`

La línea de comandos. `build_parser()` define los comandos y `main()` los ejecuta. Cada comando es una
función `cmd_*`:

- `cmd_validate`: carga y valida la configuración y muestra qué falta de la autorización.
- `cmd_diagnose` / `cmd_suggest`: piden confirmación, ejecutan el diagnóstico y guardan el informe.
- `cmd_preview`: vista previa en vivo o desde archivo.
- `cmd_run`: flujo completo con confirmación escrita (`si`) antes de extraer.
- `cmd_compare`, `cmd_init`, `cmd_gui`, `cmd_serve`, `cmd_matrix`: el resto de comandos.
- `_install_cancel_handler`: hace que `Ctrl+C` cancele de forma ordenada.

### 4.2 Configuración: `web_extractor/config/`

- **`schema.py`**: define la configuración con Pydantic. Si falta un dato o hay una clave desconocida,
  la rechaza con un mensaje por campo. Clases principales:
  - `ProjectConfig`: la configuración completa.
  - `AuthorizationConfig`: quién autoriza, finalidad, términos revisados, evidencia, entorno y
    confirmación.
  - `ScopeConfig`: dominios y rutas permitidos y respeto de robots.txt.
  - `LimitsConfig`: máximo de páginas, registros, solicitudes, tiempo, clics, scrolls y pausa.
  - `ExtractionConfig`: método (`static_html`, `browser`, `structured_file`, `api`), selectores y
    campos.
  - `FieldRule`: un campo: selector CSS, columna o ruta JSON/XML, tipo, normalizadores y validación.
  - `PaginationConfig`, `BrowserConfig` (incluye `engine`: auto, chrome o edge), `ApiConfig`,
    `AuthConfig` y `OutputConfig` (formatos csv, json, excel y sqlite).
- **`loader.py`**: `load_config()` lee YAML o JSON; `config_fingerprint()` calcula la huella SHA-256
  que identifica la configuración usada.
- **`templates.py`**: `default_config_dict(url)` crea una configuración conservadora para cualquier URL
  nueva; la usan la interfaz y el comando `init`.

### 4.3 Núcleo: `web_extractor/core/`

- **`engine.py` → `ExtractionEngine`**: el motor que coordina todo.
  - `diagnose()`: pide pocas páginas, ejecuta los inspectores, detecta barreras y clasifica métodos.
  - `_render_compare()`: con `--render`, compara el HTML inicial con el renderizado por el navegador.
  - `preview()`: obtiene una página (o un archivo local) y muestra los registros procesados.
  - `run()`: verifica la autorización, crea el adaptador, extrae, limpia, exporta e informa.
- **`authorization.py`**: `missing_for_diagnosis()` y `missing_for_extraction()` listan lo que falta;
  sin autorización completa no se hacen solicitudes de extracción.
- **`http_client.py` → `PoliteHttpClient`**: todas las solicitudes HTTP pasan por aquí. En orden:
  revisa el alcance, consulta robots.txt, descuenta del presupuesto, espera la pausa, hace la
  solicitud, valida cada redirección y detecta barreras. Solo reintenta errores de red pasajeros;
  nunca reintenta un 403, 429, CAPTCHA ni un certificado inválido.
- **`robots.py` → `RobotsPolicy`**: interpreta robots.txt según el estándar RFC 9309 y aplica el
  `Crawl-delay`.
- **`scope.py`**: `check_in_scope()` impide salir de los dominios y rutas permitidos y bloquea
  direcciones de red interna.
- **`limits.py`**: `Budget` cuenta solicitudes, páginas, registros, clics, scrolls y tiempo;
  `RateLimiter` aplica la pausa; `CancelToken` permite cancelar (botón, `Ctrl+C` o archivo
  `outputs/STOP`).
- **`barriers.py` → `detect_barrier()`**: reconoce CAPTCHA, desafío anti-bot (incluido Cloudflare),
  muro de inicio de sesión, límite de tasa, sobrecarga del servidor, acceso denegado, paywall y error
  TLS. Cada tipo tiene su
  "siguiente paso legítimo" en `NEXT_STEPS`. Un formulario de acceso opcional en una página con mucho
  contenido público no se trata como muro.
- **`auth.py`**: autenticación **solo si está autorizada**: formulario o token en encabezado. Las
  credenciales se leen de variables de entorno y nunca se escriben en logs.
- **`tracing.py`**: `ActionLog` (bitácora de acciones) e `IncidentLog` (incidencias).
- **`errors.py`**: los errores propios (`BarrierDetected`, `RobotsDisallowed`, `LimitReached`,
  `Cancelled`, etc.).

### 4.4 Inspectores (diagnóstico): `web_extractor/inspectors/`

Cada inspector revisa una respuesta y produce **hallazgos** con evidencia y pesos a favor o en contra
de cada método.

- **`response_inspector.py`**: tipo de contenido, código HTTP y encabezados (JSON, CSV, XML, HTML).
- **`html_inspector.py` → `HtmlInspector`**: el más completo. Excluye menús, encabezados y pies de
  página para no confundirlos con datos. Detecta:
  - contenedores vacíos y marcadores de frameworks JavaScript (React, Vue, Angular, Next…);
  - DOM inicial mínimo con varios scripts (`js.thin_dom`);
  - llamadas XHR/fetch y GraphQL (solo las reporta, no las llama);
  - tablas, estructuras repetidas (candidatas a registro) y paginación;
  - botón "cargar más" y scroll infinito;
  - elementos que requieren interacción (pestañas, `onclick`, `aria-expanded`);
  - contenido que depende del tiempo (enlaces con `fecha=`, meta refresh, WebSocket);
  - formularios de inicio de sesión.
- **`structured_inspector.py`**: en JSON y XML encuentra la lista de registros y sus campos; en CSV, las
  columnas.
- **`classifier.py` → `classify()`**: suma los pesos de los hallazgos y ordena los métodos con
  puntuación y confianza (`confidence_label`). Nunca declara certeza (tope de 0.95). Una API solo es
  ejecutable si el usuario declaró su documentación pública.

### 4.5 Extractores (adaptadores): `web_extractor/extractors/`

Todos implementan la misma interfaz (`iter_documents()` y `close()`), por eso el motor los intercambia.

- **`static_html.py` → `StaticHtmlAdapter`**: Requests + BeautifulSoup; paginación por enlace
  "siguiente" o por plantilla de URL.
- **`browser_selenium.py` → `SeleniumBrowserAdapter`**: Selenium con Edge o Chrome headless.
  `available_browsers()` detecta qué navegador hay. Espera un selector, hace clic en "cargar más" o
  scroll infinito con topes, y revisa barreras en cada paso. No oculta que es un navegador
  automatizado.
- **`structured_file.py` → `StructuredFileAdapter`**: descarga archivos CSV, JSON o XML públicos.
- **`api_json.py` → `DocumentedApiAdapter`**: APIs públicas y documentadas, con paginación por
  parámetro o por campo "siguiente".
- **`registry.py` → `create_adapter()`**: elige el adaptador según el método.

### 4.6 Selección de campos: `web_extractor/selection/`

- **`field_extractor.py`**: `parse_document()` detecta el formato y aplica las reglas:
  `parse_html_records` (selectores CSS), `parse_html_table` (columnas de tabla),
  `parse_json_records`, `parse_xml_records` y `parse_csv_records`.
- **`xml_data.py` → `xml_to_data()`**: convierte XML en la misma estructura que JSON, así las rutas
  son iguales (`country.text`, `country.@id`).
- **`paths.py`**: `get_path()` lee rutas como `data.items.0.nombre`.
- **`suggest.py` → `suggest_extraction()`**: genera el borrador de campos a partir del diagnóstico
  (título, enlace y valores; evita contenedores de maquetación).

### 4.7 Limpieza y calidad: `web_extractor/transforms/`

- **`normalizers.py`**: 12 normalizadores (`strip`, `collapse_whitespace`, `remove_currency`,
  `decimal_comma`, `empty_to_none`…).
- **`casting.py` → `cast_value()`**: convierte a entero, decimal, booleano, fecha o URL.
- **`validators.py` → `validate_value()`**: regex, mínimo/máximo, opciones y longitud.
- **`pipeline.py` → `TransformPipeline`**: aplica, por campo, normalizar → patrón → tipo → validar;
  elimina duplicados (`_deduplicate`) y arma el **linaje** de cada registro: URL, fecha, método,
  página, estado de validación, transformaciones, campo de origen (`field_sources`), run_id y huella de
  la configuración.

### 4.8 Almacenamiento: `web_extractor/storage/exporters.py`

`CsvExporter`, `JsonExporter`, `ExcelExporter` (hojas `datos` e `incidencias`) y `SqliteExporter`
(tablas `runs`, `records`, `incidents`). `export_all()` genera los formatos configurados.

### 4.9 Informes: `web_extractor/reports/`

- **`diagnosis_report.py`**: informe Markdown del diagnóstico (métodos, evidencia, incidencias,
  limitaciones).
- **`run_report.py`**: `report.md` y `summary.json` de cada ejecución, con siguientes pasos.
- **`profiles.py`**: `build_profile()` guarda la "huella" del sitio (selectores, campos, columnas,
  estructura JSON, volumen, endpoint documentado). `compare_profiles()` detecta cambios, y
  `requires_review()` exige revisión humana si son graves.

### 4.10 Interfaz gráfica: `web_extractor/gui/`

- **`app.py`**: interfaz Streamlit con 7 pestañas (`tab_project`, `tab_scope`, `tab_diagnosis`,
  `tab_fields`, `tab_preview`, `tab_run`, `tab_results`). No tiene lógica propia de extracción:
  arma la misma configuración y llama al mismo `ExtractionEngine`. Los botones que harían solicitudes
  se desactivan si falta la autorización.
- **`jobs.py` → `ExtractionJob`**: ejecuta la extracción en segundo plano para mostrar el progreso en
  vivo y permitir **Cancelar**.

### 4.11 Otros

- **`models/results.py`**: estructuras de datos compartidas (`Diagnosis`, `Finding`, `Incident`,
  `RunResult`, `QualityReport`…).
- **`interface/console.py`**: mensajes y preguntas de la CLI (`ask_yes_no` exige escribir "si").
- **`utils/redaction.py`**: oculta contraseñas y tokens en cualquier salida.
- **`devtools/fixture_server.py`** y **`devtools/matrix.py`**: sitio de pruebas local y matriz de 20
  casos.

## 5. Dónde se cumple cada requisito de la asignación

### 5.1 Los 7 módulos del reto

| Módulo pedido | Dónde está |
|---|---|
| 1. Diagnóstico de la fuente | `core/engine.py` (`diagnose`), `inspectors/*`, `reports/diagnosis_report.py` |
| 2. Recomendación del método | `inspectors/classifier.py` (puntuación, confianza y requisitos) |
| 3. Selección de campos | `selection/suggest.py`, `selection/field_extractor.py`, pestaña 4 de la GUI |
| 4. Extracción | `extractors/*` (HTML estático, Selenium, archivo, API) con `core/limits.py` |
| 5. Limpieza y validación | `transforms/*` |
| 6. Almacenamiento y exportación | `storage/exporters.py` (CSV, JSON, Excel, SQLite) |
| 7. Informes y monitoreo | `reports/*`, `core/tracing.py`, detección de cambios en `reports/profiles.py` |

### 5.2 Detecciones pedidas

| Detección | Dónde |
|---|---|
| HTML estático o dinámico, frameworks JS | `html_inspector.py` (contenedores vacíos, frameworks, `js.thin_dom`) y `--render` |
| API REST / GraphQL, XHR/Fetch | `html_inspector.py` (indicios, sin llamar endpoints), `api_json.py` para APIs documentadas |
| Scroll infinito, paginación, "cargar más" | `html_inspector.py` y `browser_selenium.py` |
| Contenido por eventos / interacción / AJAX | `html_inspector.py` (`dom.interaction`) |
| Archivos JSON, XML y CSV | `response_inspector.py`, `structured_inspector.py` |
| Autenticación y sesiones | `html_inspector.py` (formularios), `core/auth.py` (solo autorizada) |
| CAPTCHA y bloqueos | `core/barriers.py` |
| Contenido dependiente del tiempo | `html_inspector.py` (`time.dependent`) |

### 5.3 Escenarios de aceptación

| Escenario | Evidencia |
|---|---|
| Página estática | Real: datos.gob.mx (r01), DOF (r05). Fixture: T01 |
| Contenido con JavaScript | Real: catalog.data.gov con Edge (r04). Fixture: T03 |
| API documentada | Real: Banco Mundial JSON (r02). Fixture: T06, T20 |
| Paginación | Real: r01 y r02 (2 páginas cada uno). Fixture: T01, T06 |
| Scroll infinito / bajo demanda | Fixture: T04 ("cargar más") y T05 (scroll) |
| Tablas | Fixture: T02 |
| Autenticación autorizada | Fixture: T08, T19, T20 |
| CAPTCHA / bloqueo genera incidencia | Real: INEGI (r07), data.worldbank.org (r06), www.dof.gob.mx (r08). Fixture: T09, T10, T11 |

Los escenarios marcados solo como fixture no aparecen de forma legítima en los sitios reales
probados; se demuestran con el sitio de pruebas local.

### 5.4 Puntos extra (plus)

| Punto | Dónde |
|---|---|
| Perfilado de datos | `summary.json` → `quality` (tasa de llenado por campo); `reports/profiles.py` |
| Detección de cambios | `reports/profiles.py` (selectores, campos eliminados, columnas nuevas, estructura JSON, volumen, endpoint) |
| Linaje | `transforms/pipeline.py`: URL, fecha, método, campo de origen, estado de validación, transformaciones y run_id |

### 5.5 Requisitos generales y entregables

| Requisito | Cumplimiento |
|---|---|
| Al menos 5 sitios | 5 portales reales: datos.gob.mx, Banco Mundial, data.gov, DOF e INEGI (`examples/reales/`) |
| Al menos 4 mecanismos | HTML estático, Selenium (JavaScript), API REST, archivo XML |
| Motor reutilizable, sin modificar para URLs nuevas | Un solo `ExtractionEngine`; la GUI acepta cualquier URL |
| Interfaz intuitiva | GUI de 7 pestañas con lista de lo que falta y botones guiados |
| Sin datos ficticios en la evaluación | Corridas reales en `docs/evidencias/reales/` |
| Evidencia de diagnóstico y extracción | `docs/evidencias/reales/<sitio>/diagnostico.md`, `report.md`, datos |
| Informe de restricciones por sitio | `docs/evidencias/reales/README.md` (protección y viabilidad legal) |
| Sin pruebas masivas | Topes bajos (2 páginas, ≤ 60 registros), pausa de 2 a 10 s, concurrencia 1 |
| Código con Selenium | `extractors/browser_selenium.py` |
| Dataset SQLite, CSV y Excel | `docs/evidencias/reales/dataset_reales.sqlite` y `.xlsx`; CSV por sitio |
| Informe técnico | `docs/informe_tecnico.md` |
| Video de 3 a 5 minutos | Guion en `docs/guion_demo.md` (la grabación la hace el equipo) |
| Requisitos no funcionales | Seguridad (sin secretos, alcance, robots), límites, cancelación y pruebas (207 + matriz de 20) |
| Plan en 5 fases | `docs/plan_fases.md` |

## 6. Límites éticos y legales que aplica el sistema

- Solo trabaja con autorización declarada y confirmada.
- Respeta robots.txt, el `Crawl-delay`, el alcance y los límites configurados.
- No evade CAPTCHA, bloqueos, inicios de sesión, paywalls ni certificados inválidos: se detiene y lo
  registra.
- No usa proxies, suplantación de identidad ni técnicas para ocultar la automatización.
- No acepta campos con datos sensibles (CURP, RFC, tarjetas, contraseñas) ni secretos en la
  configuración.
- No inventa ni llama endpoints de API que no estén documentados.

## 7. Documentos relacionados

- `README.md`: resumen e instalación.
- `docs/manual_usuario.md`: manual detallado y solución de errores.
- `docs/informe_tecnico.md`: arquitectura, decisiones, resultados y limitaciones.
- `docs/matriz_pruebas.md`: matriz de pruebas y criterios de aceptación.
- `docs/evidencias/reales/README.md`: evidencia de los sitios reales.
- `docs/guion_demo.md`: guion del video.
