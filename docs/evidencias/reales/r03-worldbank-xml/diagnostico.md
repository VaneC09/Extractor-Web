# Diagnóstico de `https://api.worldbank.org/v2/country/MX;US;CA/indicator/NY.GDP.MKTP.CD?date=2015:2024&per_page=50`

- Fecha (UTC): 2026-11-21T20:32:36Z
- URL final: https://api.worldbank.org/v2/country/MX;US;CA/indicator/NY.GDP.MKTP.CD?date=2015:2024&per_page=50
- Estado HTTP: 200
- Tipo de contenido: text/xml
- Solicitudes usadas: 2
- Diagnóstico detenido: no

## Métodos sugeridos

| Método | Puntuación | Confianza | Ejecutable | Requisitos |
|---|---|---|---|---|
| structured_file | 0.70 | media | sí | Confirmar que el archivo es público, autorizado y su licencia permite el uso |
| static_html | 0.00 | baja | sí | — |
| browser | 0.00 | baja | sí | Requiere Selenium con Chrome o Edge; mayor coste por página: usar topes bajos |
| api | 0.00 | baja | no verificado / no ejecutar | No verificado / no ejecutar: falta confirmar una API pública y documentada (extraction.api.documented + documentation_url) |

### structured_file
- A favor: La URL entrega XML directamente (+0.70)

### static_html
- En contra: La URL entrega XML directamente (-0.35)

### browser
- En contra: La URL entrega XML directamente (-0.15)

## Hallazgos (indicios heurísticos)

| Código | Categoría | Descripción | Evidencia |
|---|---|---|---|
| response.status | respuesta | HTTP 200, text/xml, 8,683 caracteres | vía http |
| response.xml | estructurado | La URL entrega XML directamente | text/xml |
| json.records | estructurado | XML: lista de 30 registros en 'data' | country, country.@id, country.text, countryiso3code, date, decimal, indicator, indicator.@id, indicator.text, obs_status, unit, value |

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
  "data_format": "xml",
  "records_paths": [
    {
      "path": "data",
      "count": 30
    }
  ],
  "json_fields": [
    "country",
    "country.@id",
    "country.text",
    "countryiso3code",
    "date",
    "decimal",
    "indicator",
    "indicator.@id",
    "indicator.text",
    "obs_status",
    "unit",
    "value"
  ]
}
```
