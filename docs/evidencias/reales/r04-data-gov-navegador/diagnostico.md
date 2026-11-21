# Diagnóstico de `https://catalog.data.gov/`

- Fecha (UTC): 2026-11-21T20:38:22Z
- URL final: https://catalog.data.gov/
- Estado HTTP: 200
- Tipo de contenido: text/html; charset=utf-8
- Solicitudes usadas: 2
- Diagnóstico detenido: no

## Métodos sugeridos

| Método | Puntuación | Confianza | Ejecutable | Requisitos |
|---|---|---|---|---|
| browser | 0.60 | media | sí | Requiere Selenium con Chrome o Edge; mayor coste por página: usar topes bajos |
| static_html | 0.55 | media | sí | — |
| structured_file | 0.00 | baja | sí | Confirmar que el archivo es público, autorizado y su licencia permite el uso |
| api | 0.00 | baja | no verificado / no ejecutar | No verificado / no ejecutar: falta confirmar una API pública y documentada (extraction.api.documented + documentation_url) |

### browser
- A favor: Los scripts cargan datos de forma asíncrona (fetch/XHR). No se infieren ni se llaman sus endpoints: no están documentados (+0.10)
- A favor: Control 'cargar más' (button sin enlace: requiere clic) (+0.30)
- A favor: 14 elemento(s) que muestran contenido al interactuar (pestañas, desplegables, clics): ese contenido puede no estar en el HTML inicial (+0.10)

### static_html
- A favor: Hay texto sustancial en el HTML inicial (+0.20)
- A favor: Estructura repetida candidata a registro: 'li.usa-collection__item.organization-datasets__item.margin-0' ×20 (+0.15)
- En contra: Control 'cargar más' (button sin enlace: requiere clic) (-0.10)

## Hallazgos (indicios heurísticos)

| Código | Categoría | Descripción | Evidencia |
|---|---|---|---|
| response.status | respuesta | HTTP 200, text/html; charset=utf-8, 230,456 caracteres | vía http |
| html.summary | dom | Título: 'Catalog - Data.gov'; 1049 elementos; 12,923 caracteres de texto visible; 17 scripts | Skip to main content An official website of the United States government Here’s how you know Here’s how you know Official websites use .gov A .gov website belon |
| html.text_present | dom | Hay texto sustancial en el HTML inicial | 12923 caracteres |
| js.async_load | renderizado | Los scripts cargan datos de forma asíncrona (fetch/XHR). No se infieren ni se llaman sus endpoints: no están documentados |  |
| html.repeated | estructura | Estructura repetida candidata a registro: 'li.usa-collection__item.organization-datasets__item.margin-0' ×20 | a.label.label-default.text-uppercase, a.usa-link, li.usa-collection__meta-item, div.organization-datasets__body, div.dataset-org-banner.organization-datasets__b |
| html.load_more | bajo demanda | Control 'cargar más' (button sin enlace: requiere clic) | <button class="usa-button margin-top-2" hx-get="/api/v1/search?q=&amp;sort=relevance&amp;per_page=20&amp;after=WzEuMCw3NzcsIjI1ZTRlN2I4LTM0MWQtNGNhYS05MjIyLWI4O |
| dom.interaction | interacción | 14 elemento(s) que muestran contenido al interactuar (pestañas, desplegables, clics): ese contenido puede no estar en el HTML inicial | button.usa-accordion__button.usa-banner__button, button.usa-button.usa-button--outline.filter-mobile-trigger, button.usa-button.usa-button--outline, button.usa- |
| html.meta_robots | política | Meta robots declarado | index,follow |

## Limitaciones del diagnóstico

- Se analiza una sola respuesta del documento objetivo (más robots.txt); el contenido puede variar por usuario, región, hora o pruebas A/B.
- Sin render opcional no se ejecuta JavaScript: los indicios de renderizado en cliente son heurísticos.
- No se exploran rutas no enlazadas ni se infieren o prueban endpoints/APIs no documentados.
- La detección de CAPTCHA, bloqueos o protecciones es heurística: puede haber falsos positivos y negativos.
- La herramienta no puede verificar la autorización legal ni los términos de uso; dependen de la confirmación humana registrada en la configuración.
- Crawl-delay 10s aplicado
- https://catalog.data.gov/robots.txt leído

## Candidatos detectados

```json
{
  "record_selectors": [
    {
      "selector": "li.usa-collection__item.organization-datasets__item.margin-0",
      "count": 20,
      "avg_text": 426,
      "child_selectors": [
        "a.label.label-default.text-uppercase",
        "a.usa-link",
        "li.usa-collection__meta-item",
        "div.organization-datasets__body",
        "div.dataset-org-banner.organization-datasets__body--state",
        "span.dataset-org-banner__rank",
        "span.dataset-org-banner__type",
        "div.dataset-content"
      ],
      "has_link": true
    },
    {
      "selector": "button.tag-link.tag-link--suggested.tag-link--publisher",
      "count": 10,
      "avg_text": 48,
      "child_selectors": [
        "span.tag-link__count"
      ],
      "has_link": false
    },
    {
      "selector": "button.tag-link.tag-link--suggested.tag-link--organization",
      "count": 10,
      "avg_text": 42,
      "child_selectors": [
        "span.tag-link__count"
      ],
      "has_link": false
    },
    {
      "selector": "button.tag-link.tag-link--suggested",
      "count": 10,
      "avg_text": 22,
      "child_selectors": [
        "span.tag-link__count"
      ],
      "has_link": false
    },
    {
      "selector": "div.usa-accordion.usa-accordion--bordered.filter-accordion",
      "count": 7,
      "avg_text": 265,
      "child_selectors": [
        "h3.usa-accordion__heading",
        "button.usa-accordion__button",
        "span.filter-accordion__heading-text",
        "span.filter-accordion__title",
        "div.usa-accordion__content.usa-prose",
        "div.keyword-autocomplete",
        "label.usa-label",
        "span.usa-hint"
      ],
      "has_link": false
    }
  ]
}
```
