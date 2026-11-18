# Informe técnico

## 1. Objetivo y alcance

Construir una herramienta reutilizable que, para una URL **autorizada**, diagnostique cómo se
entrega la información, proponga un método de adquisición con evidencia y confianza, permita a una
persona definir campos y reglas, extraiga dentro de límites, limpie y valide, conserve linaje y
genere informes. El alcance del MVP excluye cualquier técnica de evasión, la autenticación con
navegador y bases de datos de servidor.

### Datos imprescindibles que faltan (y supuestos)

| Dato | Estado | Supuesto mientras falta |
|---|---|---|
| URLs reales aprobadas | No proporcionadas | Se usan 11 escenarios de fixtures locales controlados |
| Confirmación de autorización por URL (quién, finalidad, términos, evidencia, vigencia) | No proporcionada | La plantilla `examples/plantilla_sitio_autorizado.yaml` queda con `confirmed: false` y bloquea la extracción |
| Límites de frecuencia aceptados por cada propietario | No proporcionados | Pausa ≥ 1 s en remoto (3 s en la plantilla), concurrencia 1, ≤ 5 solicitudes por defecto |
| Credenciales autorizadas | No aplican aún | Solo credenciales ficticias del entorno de prueba, por variables de entorno |
| Campos de interés reales | No proporcionados | Campos ficticios por escenario |

## 2. Arquitectura

```
          ┌──────────── interface/console + app.py (CLI guiada) ────────────┐
          │                                                                 │
config/ ──► core/engine.ExtractionEngine ──► reports/ (diagnóstico, ejecución, perfiles)
          │      │        │        │                      ▲
          │      │        │        └─► storage/ (CSV, JSON, SQLite)
          │      │        └─► transforms/ (normalizar → tipo → validar → deduplicar → linaje)
          │      └─► selection/ (reglas de campos sobre HTML, tabla, JSON, CSV)
          │
          ├─► inspectors/ (respuesta, HTML, estructurado) → classifier
          └─► extractors/ (static_html | browser | structured_file | api)
                     │
                     └─► core/http_client (alcance → robots → presupuesto → pausa → solicitud
                                           → redirecciones validadas → barreras → reintento transitorio)
```

Interfaces (protocolos) principales:

| Interfaz | Archivo | Implementaciones |
|---|---|---|
| `Inspector` (`applies_to`, `inspect`) | `inspectors/base.py` | `ResponseInspector`, `HtmlInspector`, `StructuredInspector` |
| `Adapter` (`iter_documents`, `close`) | `extractors/base.py` | `StaticHtmlAdapter`, `SeleniumBrowserAdapter`, `StructuredFileAdapter`, `DocumentedApiAdapter` |
| Normalizador `str -> str/None` | `transforms/normalizers.py` | 12 registrados por nombre |
| Validador declarativo | `transforms/validators.py` | regex, min/max, choices, longitudes |
| `Exporter` (`export`) | `storage/exporters.py` | `CsvExporter`, `JsonExporter`, `SqliteExporter` |
| Informes | `reports/*` | diagnóstico (MD/JSON), ejecución (MD/JSON), perfiles |

Separación de responsabilidades: la configuración solo describe; el núcleo decide políticas; los
adaptadores solo adquieren documentos; `selection` solo interpreta; `transforms` solo limpia;
`storage` solo persiste; `interface`/`app` solo presentan y preguntan. No hay selectores ni URLs
de sitios concretos en el código: los once escenarios usan el mismo motor con YAML distintos.

## 3. Decisiones técnicas

| Decisión | Motivo |
|---|---|
| Pydantic v2 con `extra="forbid"` | Validación declarativa con mensajes por campo; impide claves desconocidas como `password:` |
| Expansión de variables restringida a `WE_*`/`FIXTURE_*` sin nombres tipo secreto | Reutilizar configuraciones sin introducir credenciales en objetos que se resumen en informes |
| Redirecciones manuales | Cada salto se valida contra el alcance **antes** de solicitarlo |
| Lectura de respuesta con tope de bytes | Evitar descargas excesivas (`max_response_bytes`) |
| Reintentos solo para errores de red, 502 y 504 | 429/403/503/401 y CAPTCHA son señales de parada, no fallos transitorios |
| robots.txt según RFC 9309 | 4xx = sin restricciones; 5xx/red = prohibición total; Crawl-delay eleva la pausa |
| Clasificador por suma de pesos con tope 0.95 | Recomendaciones explicables; nunca se declara certeza |
| Un único extractor de campos para HTTP y navegador | El navegador entrega HTML renderizado; se evita duplicar lógica |
| Selenium sin opciones anti-detección | Cumplir el requisito de no ocultar la automatización; UA honesto y configurable |
| Pandas para CSV de entrada/salida y deduplicación | Robustez con formatos y tipos; requisito del proyecto |
| SQLite con columnas JSON | Persistencia local sin servidor, consultable y acumulativa |
| Línea base de perfil solo tras ejecución correcta sin cambios graves | No "reparar" ni aceptar silenciosamente cambios de estructura |
| Paquete `selection/` en lugar de `selectors/` | Evitar sombrear el módulo estándar `selectors` |

### Versiones

Rangos en `requirements.txt`; versiones exactas probadas en `requirements-lock.txt` (instaladas
desde PyPI el 2026-11-10 en Python 3.12.3): requests 2.34.2, beautifulsoup4 4.15.0, selenium
4.52.0, pandas 3.1.1, numpy 2.5.4, pydantic 2.14.3, PyYAML 6.0.3, pytest 9.2.0; Chrome 156. Son las
versiones que resolvió pip en ese momento; no se afirma que sean "las últimas" en otra fecha. El
límite inferior de los rangos es orientativo y no se probó con versiones antiguas.

### Playwright como alternativa

Playwright ofrece esperas automáticas y control de red más fino (por ejemplo bloquear subrecursos
fuera de alcance). Puede añadirse como otro adaptador que implemente la misma interfaz `Adapter`;
no es requisito porque Selenium cubre los escenarios del MVP.

## 4. Flujo de extremo a extremo

1. `init`/edición del YAML: URL, autorización, alcance, límites.
2. `validate`: esquema, protocolo, alcance, límites, nombres sensibles; lista lo que falta.
3. `diagnose`: ≤ 3 solicitudes (robots.txt, documento y una redirección), +1 con `--render`.
4. Presentación de hallazgos, evidencia, métodos con confianza, requisitos y limitaciones.
5. `suggest` (borrador) o reglas manuales; `preview --from-file` sin solicitudes.
6. `preview` en vivo (1 página) y confirmación escrita (`si`) o `--yes` explícito.
7. `run`: adaptador con topes, pausas, cancelación (`Ctrl+C` o archivo STOP).
8. Calidad: normalización, tipos, validación, deduplicación, linaje.
9. Exportación CSV/JSON/SQLite + `report.md`, `summary.json`, `actions.jsonl`, `run.log`.
10. Estado final explícito (`completado`, `completado_con_limites`, `parcial_barrera`,
    `detenido_barrera`, `detenido_politica`, `cancelado`, `fallido`) y siguientes pasos legítimos.

## 5. Qué es heurístico y qué no se puede saber

- Renderizado con JS: se infiere de contenedores raíz vacíos, marcadores de frameworks, `<noscript>`
  y proporción texto/scripts; el render opcional lo confirma solo para esa carga concreta.
- Paginación, «cargar más» y scroll infinito: se detectan por enlaces, textos y patrones en scripts;
  pueden existir mecanismos sin indicios en el HTML.
- APIs: solo se consideran si el usuario declara documentación pública. Llamadas `fetch/XHR` en
  scripts se reportan como indicio, pero sus endpoints **no** se infieren ni se llaman.
- Barreras: códigos HTTP y marcadores textuales. Falsos positivos posibles (una página que habla de
  CAPTCHA) y falsos negativos (protecciones invisibles). Ante la duda se detiene.
- No se puede saber desde una inspección permitida: términos de uso aplicables, permisos reales,
  límites no publicados, variaciones por usuario/región, contenido tras autenticación no autorizada,
  ni el código HTTP de una navegación en Selenium.

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Uso sin autorización | Puerta de autorización + confirmación por ejecución; plantilla bloqueada por defecto |
| Carga excesiva | Concurrencia 1, pausa mínima, topes duros, parada ante 429/503, Crawl-delay |
| Fuga de secretos | Credenciales por variable de entorno, registro de secretos, filtro de logs, URLs redactadas, `extra="forbid"`; prueba que busca la contraseña en todas las salidas |
| Recopilar datos sensibles | Rechazo de nombres de campo sensibles, `personal_data: none` por defecto, minimización a campos configurados |
| Acceso a red interna (SSRF) | Rechazo de IPs privadas/loopback salvo `allow_private_network` con dominios locales |
| Selectores rotos o cambio de estructura | Perfiles, tasa de llenado, firma estructural, revisión humana obligatoria |
| Navegador colgado | Timeouts de carga y espera, presupuesto de tiempo, `quit()` en `finally` |
| Subrecursos externos en Selenium | Limitación documentada; mitigable con un adaptador Playwright que filtre peticiones |

## 7. Resultados

Ejecución de `python -m web_extractor matrix` el 2026-11-18 (UTC): **18/18 casos cumplen lo
esperado**; detalle en [evidencias/matriz_resultados.md](evidencias/matriz_resultados.md).
`python -m pytest`: 170 pruebas superadas. Incluye:

- 7 pruebas con Chrome headless.
- 7 pruebas de la interfaz gráfica con `streamlit.testing`.
- 14 pruebas de sitios no incluidos, que usan el sitio local «no visto» y una sesión HTTP simulada.

Todas las ejecuciones se hicieron **solo contra fixtures locales o respuestas simuladas**; no hay
resultados de sitios reales. Qué ocurre con un sitio que no es de los ejemplos:
[sitios_no_incluidos.md](sitios_no_incluidos.md).

### Interfaz gráfica

`web_extractor/gui/app.py` (Streamlit) es una capa de presentación: construye el mismo diccionario
de configuración, lo valida con el mismo esquema y llama a `ExtractionEngine`. No hay lógica de
extracción propia.

- `gui/jobs.py` ejecuta `run()` en un hilo. Comparte un `CancelToken` con el botón Cancelar y
  recibe cada acción mediante el gancho `on_action` del motor, para mostrar el progreso en vivo.
- Las credenciales nunca se escriben en la interfaz: solo el nombre de la variable de entorno.
- Limitación: la interfaz es local y para una sola persona. Las descargas y el historial leen
  `outputs/`. Algunos textos internos de Streamlit, como los del selector de archivos, aparecen en
  inglés.

## 8. Viabilidad legal y técnica por escenario

| Escenario | Viabilidad técnica | Viabilidad legal/uso | Condición para un sitio real |
|---|---|---|---|
| HTML estático + paginación | Alta | Depende de términos y permiso | Permiso, robots.txt, pausas ≥ 1 s |
| Tabla HTML | Alta | Igual | Igual; revisar licencia de los datos |
| Renderizado JS | Media (coste mayor, frágil) | Igual | Preferir API/archivo oficial si existe |
| «Cargar más» / scroll | Media | Igual; mayor carga por acción | Topes de clics/scrolls bajos |
| API documentada | Alta | Alta si la documentación permite el uso | Respetar cuotas y términos de la API |
| Archivo CSV/JSON | Alta | Alta con licencia abierta | Verificar licencia y vigencia |
| Autenticación | Media | Solo con autorización expresa y cuenta propia | Credenciales del usuario; nunca de terceros |
| CAPTCHA / 429 / 403 / robots | No aplica: se detiene | No se continúa | Vía alternativa autorizada por el propietario |

## 9. Extensiones previstas

Interfaz web multiusuario (la GUI actual es local); Excel,
PostgreSQL y MongoDB como exportadores adicionales; caché condicional HTTP; adaptador Playwright;
autenticación con navegador; CI.
