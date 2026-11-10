# Diagnóstico de `http://127.0.0.1:37897/static/catalogo?page=1`

- Fecha (UTC): 2026-11-10T22:55:25Z
- URL final: http://127.0.0.1:37897/static/catalogo?page=1
- Estado HTTP: 200
- Tipo de contenido: text/html; charset=utf-8
- Solicitudes usadas: 2
- Diagnóstico detenido: no

## Métodos sugeridos

| Método | Puntuación | Confianza | Ejecutable | Requisitos |
|---|---|---|---|---|
| static_html | 0.75 | alta | sí | — |
| browser | 0.10 | baja | sí | Requiere Chrome + Selenium; mayor coste por página: usar topes bajos |
| structured_file | 0.00 | baja | sí | Confirmar que el archivo es público, autorizado y su licencia permite el uso |
| api | 0.00 | baja | no verificado / no ejecutar | No verificado / no ejecutar: falta confirmar una API pública y documentada (extraction.api.documented + documentation_url) |

### static_html
- A favor: Hay texto sustancial en el HTML inicial (+0.20)
- A favor: Estructura repetida candidata a registro: 'article.product' ×4 (+0.15)
- A favor: Indicios de paginación por enlaces (+0.10)

## Hallazgos (indicios heurísticos)

| Código | Categoría | Descripción | Evidencia |
|---|---|---|---|
| response.status | respuesta | HTTP 200, text/html; charset=utf-8, 1,869 caracteres | vía http |
| html.summary | dom | Título: 'Catálogo de papelería (ficticio) — página 1'; 31 elementos; 434 caracteres de texto visible; 0 scripts | Catálogo de papelería Productos de demostración con precios ficticios para validar extracción, limpieza y paginación de HTML estático. Página 1 de 3. Cuaderno r |
| html.text_present | dom | Hay texto sustancial en el HTML inicial | 434 caracteres |
| html.repeated | estructura | Estructura repetida candidata a registro: 'article.product' ×4 | h2.product-name, span.price, span.stock, time.updated, a.detail |
| html.pagination | paginación | Indicios de paginación por enlaces | rel=next -> /static/catalogo?page=2; enlace 'Siguiente' -> /static/catalogo?page=2; contenedor de paginación |

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
  "record_selectors": [
    {
      "selector": "article.product",
      "count": 4,
      "avg_text": 62,
      "child_selectors": [
        "h2.product-name",
        "span.price",
        "span.stock",
        "time.updated",
        "a.detail"
      ],
      "has_link": true
    }
  ]
}
```
