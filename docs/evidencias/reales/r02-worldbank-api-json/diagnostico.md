# Diagnóstico de `https://api.worldbank.org/v2/country/MX/indicator/SP.POP.TOTL?format=json&per_page=20`

- Fecha (UTC): 2026-11-21T20:32:22Z
- URL final: https://api.worldbank.org/v2/country/MX/indicator/SP.POP.TOTL?format=json&per_page=20
- Estado HTTP: 200
- Tipo de contenido: application/json;charset=utf-8
- Solicitudes usadas: 2
- Diagnóstico detenido: no

## Métodos sugeridos

| Método | Puntuación | Confianza | Ejecutable | Requisitos |
|---|---|---|---|---|
| api | 0.60 | media | sí | — |
| structured_file | 0.55 | media | sí | Confirmar que el archivo es público, autorizado y su licencia permite el uso |
| static_html | 0.00 | baja | sí | — |
| browser | 0.00 | baja | sí | Requiere Selenium con Chrome o Edge; mayor coste por página: usar topes bajos |

### api
- A favor: La URL entrega JSON directamente (+0.25)
- A favor: Documentación declarada por el usuario: https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures (+0.35)

### structured_file
- A favor: La URL entrega JSON directamente (+0.55)

### static_html
- En contra: La URL entrega JSON directamente (-0.35)

### browser
- En contra: La URL entrega JSON directamente (-0.15)

## Hallazgos (indicios heurísticos)

| Código | Categoría | Descripción | Evidencia |
|---|---|---|---|
| response.status | respuesta | HTTP 200, application/json;charset=utf-8, 4,011 caracteres | vía http |
| response.json | estructurado | La URL entrega JSON directamente | application/json;charset=utf-8 |
| json.records | estructurado | JSON: lista de 2 registros en '.' | lastupdated, page, pages, per_page, sourceid, total |

## Limitaciones del diagnóstico

- Se analiza una sola respuesta del documento objetivo (más robots.txt); el contenido puede variar por usuario, región, hora o pruebas A/B.
- Sin render opcional no se ejecuta JavaScript: los indicios de renderizado en cliente son heurísticos.
- No se exploran rutas no enlazadas ni se infieren o prueban endpoints/APIs no documentados.
- La detección de CAPTCHA, bloqueos o protecciones es heurística: puede haber falsos positivos y negativos.
- La herramienta no puede verificar la autorización legal ni los términos de uso; dependen de la confirmación humana registrada en la configuración.
- https://api.worldbank.org/robots.txt devolvió 404: sin restricciones publicadas

## Candidatos detectados

```json
{
  "data_format": "json",
  "records_paths": [
    {
      "path": ".",
      "count": 2
    }
  ],
  "json_fields": [
    "lastupdated",
    "page",
    "pages",
    "per_page",
    "sourceid",
    "total"
  ]
}
```
