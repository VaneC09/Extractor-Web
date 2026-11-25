# Sitios comerciales: solo diagnóstico pasivo (2026-11-25)

Mercado Libre, Walmart México y AliExpress **no autorizaron** la extracción de datos. Por eso se usó el
modo **«Solo diagnosticar (no tengo autorización para extraer)»** de la interfaz:

- sin marcar una autorización inexistente;
- 2 solicitudes por diagnóstico (robots.txt y la página), con pausa y respetando robots.txt;
- sin extraer ni guardar datos de productos: la extracción queda bloqueada en la interfaz.

| Sitio (URL diagnosticada) | Resultado | Protección identificada | Viabilidad legal de extraer |
|---|---|---|---|
| Mercado Libre — `listado.mercadolibre.com.mx/laptop` | Detenido: redirige a un muro de verificación (`/captcha/wall/web-risk-verification` en una consulta y `/gz/account-verification` en otra) | Verificación humana o CAPTCHA antes del listado | No sin autorización. Vía legítima: API oficial para desarrolladores con token de aplicación |
| Walmart México — `www.walmart.com.mx/search?q=laptop` | HTTP 200, sin barrera en esta consulta. Next.js, indicios de GraphQL (no consultado), 199 scripts, carga diferida | Ninguna visible en 1 consulta; la ausencia de barrera no implica permiso | No sin autorización del propietario |
| AliExpress — `es.aliexpress.com/w/wholesale-laptop.html` | HTTP 200, sin barrera en esta consulta. Datos cargados con fetch/XHR (no consultados), aviso `<noscript>` | Ninguna visible en 1 consulta | No sin autorización del propietario |

Archivos:

- [mercadolibre_diagnostico.md](mercadolibre_diagnostico.md) y
  [mercadolibre_intervencion_humana.md](mercadolibre_intervencion_humana.md): barrera, «¿Se puede
  continuar? No de forma automática» y pasos.
- [walmart_diagnostico.md](walmart_diagnostico.md) y [aliexpress_diagnostico.md](aliexpress_diagnostico.md).

Hallazgo que mejoró la herramienta: la primera consulta a Mercado Libre se clasificó como
`out_of_scope` porque el muro está en otro subdominio. Ahora una redirección hacia una verificación,
un desafío anti-bot o un inicio de sesión se clasifica como esa barrera (`barrier_from_redirect` en
`core/barriers.py`) y no se sigue.

Limitación: cada sitio se consultó una o dos veces. Las protecciones pueden variar por hora, región o
frecuencia, y la detección es heurística.
