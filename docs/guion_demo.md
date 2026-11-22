# Guion de demostración (3–5 minutos)

Preparación (antes de grabar): entorno instalado y conexión a internet. Terminal 1:
`python -m web_extractor gui` (abre http://127.0.0.1:8611). Terminal 2 para la CLI. Las corridas en
sitios reales tardan unos segundos por la pausa entre solicitudes (10 s donde el sitio publica
`Crawl-delay: 10`).

| Tiempo | Acción en pantalla | Narración |
|---|---|---|
| 0:00–0:20 | `README.md`: tabla de métodos y límites de uso | "Un solo motor y configuraciones distintas. Solo datos autorizados; ante una barrera se detiene." |
| 0:20–1:30 | GUI: escribir una URL **nueva**, p. ej. `https://www.datos.gob.mx/dataset/`. Completar la autorización (quién autoriza, finalidad, términos y referencia `https://www.datos.gob.mx/robots.txt`), pulsar **Ejecutar diagnóstico** | "No se modifica nada para una URL nueva. El diagnóstico usa pocas solicitudes, lee robots.txt y, al extraer, respeta su Crawl-delay de 10 s. Recomienda HTML estático con confianza alta y muestra la evidencia." |
| 1:30–2:20 | Revisar los campos sugeridos (se cargan solos en la tabla), ajustar uno y pulsar **Vista previa en vivo** | "Las reglas son un borrador: el usuario elige los campos y ve los registros antes de extraer." |
| 2:20–3:00 | **Iniciar extracción** con tope de 2 páginas; luego **Resultados** y descarga de CSV y Excel | "Respeta los topes, valida, deduplica y guarda el linaje: URL, fecha, método, campo de origen, estado de validación, transformaciones y run_id." |
| 3:00–3:40 | CLI: `python -m web_extractor run examples/reales/r02_worldbank_api_json.yaml --yes` y `run examples/reales/r04_data_gov_navegador.yaml --yes` | "Otros mecanismos con el mismo motor: la API documentada del Banco Mundial, paginada, y data.gov con Selenium en Edge headless." |
| 3:40–4:30 | CLI: `diagnose --yes examples/reales/r07_inegi_js_captcha.yaml` y `diagnose --yes examples/reales/r06_worldbank_portal_barrera.yaml` | "INEGI carga reCAPTCHA y data.worldbank.org responde con un desafío de Cloudflare: el flujo se detiene, no reintenta y registra la incidencia con el paso legítimo, que aquí es usar la API oficial." |
| 4:30–5:00 | Mostrar `docs/evidencias/reales/README.md` y `dataset_reales.xlsx` | "Evidencia por sitio con clasificación de protección y viabilidad legal. Scroll infinito, 'cargar más' y autenticación se demuestran con fixtures porque estos sitios no los ofrecen." |

Material de apoyo: `docs/evidencias/reales/` (sitios reales), `docs/evidencias/matriz_resultados.md`
(20 escenarios con fixtures) y `examples/demo_dataset/`.
