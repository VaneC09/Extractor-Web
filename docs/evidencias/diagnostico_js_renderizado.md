# Diagnóstico de `http://127.0.0.1:37897/js/render.html`

- Fecha (UTC): 2026-11-10T22:55:23Z
- URL final: http://127.0.0.1:37897/js/render.html
- Estado HTTP: 200
- Tipo de contenido: text/html; charset=utf-8
- Solicitudes usadas: 3
- Diagnóstico detenido: no

## Métodos sugeridos

| Método | Puntuación | Confianza | Ejecutable | Requisitos |
|---|---|---|---|---|
| browser | 0.95 | alta | sí | Requiere Chrome + Selenium; mayor coste por página: usar topes bajos |
| static_html | 0.00 | baja | sí | — |
| structured_file | 0.00 | baja | sí | Confirmar que el archivo es público, autorizado y su licencia permite el uso |
| api | 0.00 | baja | no verificado / no ejecutar | No verificado / no ejecutar: falta confirmar una API pública y documentada (extraction.api.documented + documentation_url) |

### browser
- A favor: Contenedor #app vacío en el HTML inicial: contenido probablemente generado con JS (+0.45)
- A favor: Aviso <noscript> que pide habilitar JavaScript (+0.15)
- A favor: Poco texto visible frente al volumen de scripts (+0.20)
- A favor: El render con navegador añade contenido visible significativo (+0.35)

### static_html
- En contra: Contenedor #app vacío en el HTML inicial: contenido probablemente generado con JS (-0.30)
- En contra: Poco texto visible frente al volumen de scripts (-0.15)
- En contra: El render con navegador añade contenido visible significativo (-0.25)

## Hallazgos (indicios heurísticos)

| Código | Categoría | Descripción | Evidencia |
|---|---|---|---|
| response.status | respuesta | HTTP 200, text/html; charset=utf-8, 1,490 caracteres | vía http |
| html.summary | dom | Título: 'Novedades (renderizado en cliente)'; 1 elementos; 0 caracteres de texto visible; 1 scripts |  |
| js.empty_root | renderizado | Contenedor #app vacío en el HTML inicial: contenido probablemente generado con JS | <div id="app"></div> |
| js.noscript | renderizado | Aviso <noscript> que pide habilitar JavaScript | Esta página necesita JavaScript para mostrar las novedades. |
| js.low_text | renderizado | Poco texto visible frente al volumen de scripts | texto=0 scripts=1147 |
| render.adds_content | renderizado | El render con navegador añade contenido visible significativo | texto estático=34, renderizado=323 |

## Limitaciones del diagnóstico

- Se analiza una sola respuesta del documento objetivo (más robots.txt); el contenido puede variar por usuario, región, hora o pruebas A/B.
- Sin render opcional no se ejecuta JavaScript: los indicios de renderizado en cliente son heurísticos.
- No se exploran rutas no enlazadas ni se infieren o prueban endpoints/APIs no documentados.
- La detección de CAPTCHA, bloqueos o protecciones es heurística: puede haber falsos positivos y negativos.
- La herramienta no puede verificar la autorización legal ni los términos de uso; dependen de la confirmación humana registrada en la configuración.
- http://127.0.0.1:37897/robots.txt leído

## Candidatos detectados

```json
{
  "rendered_record_selectors": [
    {
      "selector": "article.card.news-item",
      "count": 5,
      "avg_text": 52,
      "child_selectors": [
        "h2.headline",
        "time.date",
        "span.category",
        "a.more"
      ],
      "has_link": true
    }
  ]
}
```
