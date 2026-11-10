# Guion de demostración (3–5 minutos)

Preparación (antes de grabar): entorno instalado, dos terminales, `outputs/` vacío.
Terminal 1: `python -m web_extractor serve-fixtures --port 8765`.

| Tiempo | Acción en pantalla | Narración |
|---|---|---|
| 0:00–0:20 | Mostrar `README.md` y la tabla de métodos | "Una herramienta, un motor, configuraciones distintas. Solo sitios autorizados; ante barreras se detiene." |
| 0:20–0:50 | `python -m web_extractor validate examples/invalida_ejemplo.yaml` y luego `validate examples/f01_catalogo_estatico.yaml` | "La configuración se valida antes de cualquier solicitud: protocolo, secretos, campos sensibles, límites. La válida muestra quién autoriza, alcance y topes." |
| 0:50–1:40 | `python -m web_extractor diagnose examples/f03_js_renderizado.yaml --render` | "El diagnóstico usa pocas solicitudes. Señala el contenedor vacío y el aviso noscript, compara con el render y recomienda navegador con confianza alta, sin afirmar certeza. Las limitaciones se muestran siempre." |
| 1:40–2:20 | `python -m web_extractor suggest examples/f02_tabla_html.yaml` y `preview examples/f02_tabla_html.yaml --from-file fixtures/site/static/tabla.html` | "Selección de campos: un borrador a partir de la tabla y una vista previa sin solicitudes, con advertencias de calidad por fila." |
| 2:20–3:20 | `python -m web_extractor run examples/f01_catalogo_estatico.yaml` → escribir `si` | "Flujo guiado: autorización, diagnóstico, vista previa y confirmación explícita. Recorre 3 páginas con pausas; elimina el duplicado y marca el producto sin SKU como inválido." Abrir `report.md` y `data.csv` (columnas `_source_url`, `_run_id`, `_validation_status`). |
| 3:20–4:00 | `python -m web_extractor run examples/f09_barrera_captcha.yaml --yes` | "Barrera: CAPTCHA detectado, parada inmediata, sin reintentos, incidencia con el paso legítimo: pedir una vía autorizada al propietario." Mostrar la sección Incidencias del informe. |
| 4:00–4:30 | `python -m web_extractor run examples/f04_cargar_mas.yaml --yes` | "Carga bajo demanda con un tope de 2 clics: 12 de 14 registros y estado 'completado con límites'." |
| 4:30–5:00 | `python -m web_extractor matrix` (o mostrar `docs/evidencias/matriz_resultados.md`) | "La matriz reproduce 16 escenarios contra fixtures locales. No se probó ningún sitio real; la tabla de sustitución espera URLs autorizadas." |

Material de apoyo: `docs/evidencias/` (informes por caso), `examples/demo_dataset/`.
