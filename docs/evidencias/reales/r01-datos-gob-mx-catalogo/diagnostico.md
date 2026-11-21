# Diagnóstico de `https://www.datos.gob.mx/dataset/?page=1`

- Fecha (UTC): 2026-11-21T20:37:27Z
- URL final: https://www.datos.gob.mx/dataset/?page=1
- Estado HTTP: 200
- Tipo de contenido: text/html; charset=utf-8
- Solicitudes usadas: 2
- Diagnóstico detenido: no

## Métodos sugeridos

| Método | Puntuación | Confianza | Ejecutable | Requisitos |
|---|---|---|---|---|
| static_html | 0.85 | alta | sí | — |
| browser | 0.20 | baja | sí | Requiere Selenium con Chrome o Edge; mayor coste por página: usar topes bajos |
| structured_file | 0.00 | baja | sí | Confirmar que el archivo es público, autorizado y su licencia permite el uso |
| api | 0.00 | baja | no verificado / no ejecutar | No verificado / no ejecutar: falta confirmar una API pública y documentada (extraction.api.documented + documentation_url) |

### static_html
- A favor: Hay texto sustancial en el HTML inicial (+0.20)
- A favor: Estructura repetida candidata a registro: 'li.resource-item.card.card-custom' ×20 (+0.15)
- A favor: Indicios de paginación por enlaces (+0.10)
- A favor: Control 'cargar más' (a con enlace) (+0.10)

### browser
- A favor: 32 elemento(s) que muestran contenido al interactuar (pestañas, desplegables, clics): ese contenido puede no estar en el HTML inicial (+0.10)

## Hallazgos (indicios heurísticos)

| Código | Categoría | Descripción | Evidencia |
|---|---|---|---|
| response.status | respuesta | HTTP 200, text/html; charset=utf-8, 74,287 caracteres | vía http |
| html.summary | dom | Título: 'Base de datos - datos.gob.mx'; 729 elementos; 8,246 caracteres de texto visible; 11 scripts | Saltar al contenido principal Trámites Gobierno Inicio Bases de datos Instituciones Categorías Visualizaciones de datos Menú Trámites Gobierno Inicio Bases de d |
| html.text_present | dom | Hay texto sustancial en el HTML inicial | 8246 caracteres |
| html.repeated | estructura | Estructura repetida candidata a registro: 'li.resource-item.card.card-custom' ×20 | p.mb-2, div.row.g-0, div.col.p-3, h3.mb-2, a.text-black |
| html.pagination | paginación | Indicios de paginación por enlaces | parámetro de página -> /dataset/?page=1; parámetro de página -> /dataset/?page=2; parámetro de página -> /dataset/?page=3; parámetro de página -> /dataset/?page |
| html.load_more | bajo demanda | Control 'cargar más' (a con enlace) | <a class="btn btn-link p-0 text-decoration-none" href="/dataset/?_organization_limit=0"> 				Mostrar más Instituciones 			</a> |
| dom.interaction | interacción | 32 elemento(s) que muestran contenido al interactuar (pestañas, desplegables, clics): ese contenido puede no estar en el HTML inicial | button.navbar-toggler, button.btn-no-style.p-0.text-decoration-none, input.form-check-input |

## Limitaciones del diagnóstico

- Se analiza una sola respuesta del documento objetivo (más robots.txt); el contenido puede variar por usuario, región, hora o pruebas A/B.
- Sin render opcional no se ejecuta JavaScript: los indicios de renderizado en cliente son heurísticos.
- No se exploran rutas no enlazadas ni se infieren o prueban endpoints/APIs no documentados.
- La detección de CAPTCHA, bloqueos o protecciones es heurística: puede haber falsos positivos y negativos.
- La herramienta no puede verificar la autorización legal ni los términos de uso; dependen de la confirmación humana registrada en la configuración.
- Crawl-delay 10s aplicado
- https://www.datos.gob.mx/robots.txt leído

## Candidatos detectados

```json
{
  "record_selectors": [
    {
      "selector": "li.resource-item.card.card-custom",
      "count": 20,
      "avg_text": 318,
      "child_selectors": [
        "p.mb-2",
        "div.row.g-0",
        "div.col.p-3",
        "h3.mb-2",
        "a.text-black",
        "a.ms-1",
        "p.mb-0",
        "a.link-pink"
      ],
      "has_link": true
    },
    {
      "selector": "section.filter.p-2",
      "count": 4,
      "avg_text": 185,
      "child_selectors": [
        "li.py-2.d-flex.align-items-start",
        "div.form-check",
        "input.form-check-input",
        "label.form-check-label",
        "span.badge.bg-gold.text-white",
        "h3.h6",
        "button.btn-no-style.p-0.text-decoration-none",
        "div.subtitle.text-black"
      ],
      "has_link": true
    },
    {
      "selector": "p.mb-2",
      "count": 4,
      "avg_text": 72,
      "child_selectors": [],
      "has_link": false
    },
    {
      "selector": "p.mb-2",
      "count": 4,
      "avg_text": 72,
      "child_selectors": [],
      "has_link": false
    },
    {
      "selector": "p.mb-2",
      "count": 4,
      "avg_text": 70,
      "child_selectors": [],
      "has_link": false
    }
  ],
  "pagination": {
    "mode": "url_template",
    "url_template": "https://www.datos.gob.mx/dataset/?page={page}"
  }
}
```
