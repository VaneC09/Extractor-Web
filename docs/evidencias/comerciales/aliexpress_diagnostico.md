# Diagnóstico de `https://es.aliexpress.com/w/wholesale-laptop.html`

- Fecha (UTC): 2026-11-25T18:57:09Z
- URL final: https://es.aliexpress.com/w/wholesale-laptop.html
- Estado HTTP: 200
- Tipo de contenido: text/html;charset=utf-8
- Solicitudes usadas: 2
- Diagnóstico detenido: no

## Métodos sugeridos

| Método | Puntuación | Confianza | Ejecutable | Requisitos |
|---|---|---|---|---|
| static_html | 0.65 | media | sí | Falta confirmar autorización antes de extraer |
| browser | 0.35 | baja | sí | Requiere Selenium con Chrome o Edge; mayor coste por página: usar topes bajos; Falta confirmar autorización antes de extraer |
| structured_file | 0.00 | baja | sí | Confirmar que el archivo es público, autorizado y su licencia permite el uso; Falta confirmar autorización antes de extraer |
| api | 0.00 | baja | no verificado / no ejecutar | No verificado / no ejecutar: falta confirmar una API pública y documentada (extraction.api.documented + documentation_url); Falta confirmar autorización antes de extraer |

### static_html
- A favor: Hay texto sustancial en el HTML inicial (+0.20)
- A favor: Estructura repetida candidata a registro: 'div.list--gallery--C2f2tvm.search-item-card-wrapper-gallery' ×12 (+0.15)

### browser
- A favor: Aviso <noscript> que pide habilitar JavaScript (+0.15)
- A favor: Los scripts cargan datos de forma asíncrona (fetch/XHR). No se infieren ni se llaman sus endpoints: no están documentados (+0.10)

## Hallazgos (indicios heurísticos)

| Código | Categoría | Descripción | Evidencia |
|---|---|---|---|
| response.status | respuesta | HTTP 200, text/html;charset=utf-8, 835,812 caracteres | vía http |
| html.summary | dom | Título: 'Laptop-Compra con envío gratis en AliExpress'; 1195 elementos; 13,616 caracteres de texto visible; 25 scripts | Windows 11, Notebook i9 Laptop Portable, 2TB 1TB SSD, 16GB RAM, intel Core i9-10980HK, PC Computer Laptop 1920*1080, 15.6 inch 3 vendidos 5 MX$4,214.02 MX$ 4 ,  |
| js.noscript | renderizado | Aviso <noscript> que pide habilitar JavaScript | Your browser does not support JavaScript! |
| html.text_present | dom | Hay texto sustancial en el HTML inicial | 13616 caracteres |
| js.async_load | renderizado | Los scripts cargan datos de forma asíncrona (fetch/XHR). No se infieren ni se llaman sus endpoints: no están documentados |  |
| html.repeated | estructura | Estructura repetida candidata a registro: 'div.list--gallery--C2f2tvm.search-item-card-wrapper-gallery' ×12 | div.new--serviceItem--1sOKrof, div.new--title--194-IOz.new--two--lN-8Suv, h3.new--titleText--3nYCLI5, div.new--tradeContainer--1v44DAh, span.new--tradeWrapper-- |
| time.dependent | tiempo | El contenido depende del momento de la consulta (actualización, caducidad o fecha). Cada registro guarda su fecha de adquisición; repetir la extracción puede dar otros datos | countDown |
| html.meta_robots | política | Meta robots declarado | follow,index |

## Limitaciones del diagnóstico

- Se analiza una sola respuesta del documento objetivo (más robots.txt); el contenido puede variar por usuario, región, hora o pruebas A/B.
- Sin render opcional no se ejecuta JavaScript: los indicios de renderizado en cliente son heurísticos.
- No se exploran rutas no enlazadas ni se infieren o prueban endpoints/APIs no documentados.
- La detección de CAPTCHA, bloqueos o protecciones es heurística: puede haber falsos positivos y negativos.
- La herramienta no puede verificar la autorización legal ni los términos de uso; dependen de la confirmación humana registrada en la configuración.
- https://es.aliexpress.com/robots.txt leído

## Candidatos detectados

```json
{
  "record_selectors": [
    {
      "selector": "div.list--gallery--C2f2tvm.search-item-card-wrapper-gallery",
      "count": 12,
      "avg_text": 270,
      "child_selectors": [
        "div.new--serviceItem--1sOKrof",
        "div.new--title--194-IOz.new--two--lN-8Suv",
        "h3.new--titleText--3nYCLI5",
        "div.new--tradeContainer--1v44DAh",
        "span.new--tradeWrapper--IqsmFRI",
        "span.new--trade--2ZrncUv",
        "span.new--starScore--2Pl3Iwj",
        "span.new--starRating--1vTvZDw"
      ],
      "has_link": true
    },
    {
      "selector": "div.relatedSearch--linkWrapper--q5Vy-5j",
      "count": 7,
      "avg_text": 14,
      "child_selectors": [
        "div.relatedSearch--item--2atTKrN",
        "a.relatedSearch--link--3gvfDG2"
      ],
      "has_link": true
    }
  ]
}
```
