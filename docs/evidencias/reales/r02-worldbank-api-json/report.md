# Informe de ejecución `20261121T203225Z-f50691`

- Proyecto: **r02-worldbank-api-json**
- URL objetivo: https://api.worldbank.org/v2/country/MX/indicator/SP.POP.TOTL?format=json&per_page=20
- Método: `api`
- Estado: **completado_con_limites** — Completado parcialmente: se alcanzó un límite configurado
- Detalle: Límite alcanzado: max_records (40)
- Inicio / fin (UTC): 2026-11-21T20:32:25Z / 2026-11-21T20:32:29Z
- Configuración (SHA-256): `08f436efe5e48f16f6d7f324b47644030f82027505e4320c0a5c861fd3f6ffad` — copia en `config_efectiva.json`
- Versión de la herramienta: 0.1.0
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Banco Mundial — Indicators API pública y documentada (licencia CC BY 4.0)",
    "purpose": "Reto final académico: serie histórica de población",
    "terms_reviewed": true,
    "environment": "production",
    "evidence_reference": "https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures",
    "allow_authentication": false,
    "valid_until": null
  },
  "scope": {
    "allowed_domains": [
      "api.worldbank.org"
    ],
    "allowed_path_prefixes": [
      "/v2/"
    ],
    "allowed_schemes": [
      "https"
    ],
    "allow_private_network": false,
    "respect_robots_txt": true
  }
}
```

## Consumo frente a límites

| Recurso | Usado | Límite |
|---|---|---|
| Solicitudes/acciones | 3 | 4 |
| Páginas | 2 | 2 |
| Registros crudos | 40 | 40 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 4.38 | 60.0 |

## Calidad de datos

- Registros crudos: 40; exportados: 40
- Válidos: 40; con advertencias: 0; inválidos: 0
- Duplicados eliminados: 0; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| pais | 40 | 0 | 0 | 100% |
| codigo_pais | 40 | 0 | 0 | 100% |
| anio | 40 | 0 | 0 | 100% |
| poblacion | 40 | 0 | 0 | 100% |

## Incidencias

- **limit** (baja) Límite alcanzado: max_records (40) — https://api.worldbank.org/v2/country/MX/indicator/SP.POP.TOTL?format=json&per_page=20 — Siguiente paso: Ampliar límites solo dentro de lo autorizado.

## Notas

- Perfil 'r02-worldbank-api-json' actualizado como línea base.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs\r02-worldbank-api-json\20261121T203225Z-f50691\data.csv`
- json: `outputs\r02-worldbank-api-json\20261121T203225Z-f50691\data.json`
- excel: `outputs\r02-worldbank-api-json\20261121T203225Z-f50691\data.xlsx`
- sqlite: `outputs\web_extractor.sqlite`
- actions: `outputs\r02-worldbank-api-json\20261121T203225Z-f50691\actions.jsonl`
- log: `outputs\r02-worldbank-api-json\20261121T203225Z-f50691\run.log`
- profile: `outputs\r02-worldbank-api-json\20261121T203225Z-f50691\profile.json`
- config: `outputs\r02-worldbank-api-json\20261121T203225Z-f50691\config_efectiva.json`

## Siguientes pasos

- Ampliar límites solo dentro de lo autorizado.
- Si necesita más datos, amplíe límites solo dentro de lo autorizado y con pausas adecuadas.
