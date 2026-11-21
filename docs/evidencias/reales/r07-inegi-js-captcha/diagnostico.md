# Diagnóstico de `https://www.inegi.org.mx/datosabiertos/`

- Fecha (UTC): 2026-11-21T21:07:03Z
- URL final: https://www.inegi.org.mx/datosabiertos/
- Estado HTTP: 200
- Tipo de contenido: text/html
- Solicitudes usadas: 3
- Diagnóstico detenido: sí

## Incidencias

- **captcha** — Indicios de CAPTCHA en la página — evidencia: ipt><script src="https://www.google.com/recaptcha/api.js?hl=es&amp;onload=onloadCallback&amp; (https://www.inegi.org.mx/datosabiertos/). Siguiente paso legítimo: Solicitar al propietario del sitio una vía autorizada (API, exportación o permiso explícito). No resolver ni evadir el CAPTCHA.

## Métodos sugeridos

| Método | Puntuación | Confianza | Ejecutable | Requisitos |
|---|---|---|---|---|
| browser | 0.45 | baja | sí | Requiere Selenium con Chrome o Edge; mayor coste por página: usar topes bajos; Falta confirmar autorización antes de extraer |
| static_html | 0.10 | baja | sí | Falta confirmar autorización antes de extraer |
| structured_file | 0.00 | baja | sí | Confirmar que el archivo es público, autorizado y su licencia permite el uso; Falta confirmar autorización antes de extraer |
| api | 0.00 | baja | no verificado / no ejecutar | No verificado / no ejecutar: falta confirmar una API pública y documentada (extraction.api.documented + documentation_url); Falta confirmar autorización antes de extraer |

### browser
- A favor: HTML inicial casi vacío con varios scripts: el contenido probablemente se carga con JavaScript/AJAX. Confírmelo con el render del navegador (+0.35)

### static_html
- En contra: HTML inicial casi vacío con varios scripts: el contenido probablemente se carga con JavaScript/AJAX. Confírmelo con el render del navegador (-0.20)

## Hallazgos (indicios heurísticos)

| Código | Categoría | Descripción | Evidencia |
|---|---|---|---|
| response.status | respuesta | HTTP 200, text/html, 3,545 caracteres | vía http |
| html.summary | dom | Título: 'Datos abiertos'; 46 elementos; 318 caracteres de texto visible; 6 scripts | Inicio / Sistemas de Consulta / Datos abiertos Datos abiertos En esta sección podrás descargar los archivos de información estadística y geográfica con formato  |
| js.thin_dom | renderizado | HTML inicial casi vacío con varios scripts: el contenido probablemente se carga con JavaScript/AJAX. Confírmelo con el render del navegador | 46 elementos, 6 scripts |
| html.meta_robots | política | Meta robots declarado | index, follow |

## Limitaciones del diagnóstico

- Se analiza una sola respuesta del documento objetivo (más robots.txt); el contenido puede variar por usuario, región, hora o pruebas A/B.
- Sin render opcional no se ejecuta JavaScript: los indicios de renderizado en cliente son heurísticos.
- No se exploran rutas no enlazadas ni se infieren o prueban endpoints/APIs no documentados.
- La detección de CAPTCHA, bloqueos o protecciones es heurística: puede haber falsos positivos y negativos.
- La herramienta no puede verificar la autorización legal ni los términos de uso; dependen de la confirmación humana registrada en la configuración.
- https://www.inegi.org.mx/robots.txt leído
