# Informe de ejecución `20261121T203238Z-0d985b`

- Proyecto: **r03-worldbank-xml**
- URL objetivo: https://api.worldbank.org/v2/country/MX;US;CA/indicator/NY.GDP.MKTP.CD?date=2015:2024&per_page=50
- Método: `structured_file`
- Estado: **completado** — Completado dentro de los límites
- Detalle: Extracción finalizada sin incidencias
- Inicio / fin (UTC): 2026-11-21T20:32:38Z / 2026-11-21T20:32:41Z
- Configuración (SHA-256): `f5a022adae19701062fea1e6db7c4fd0dbc4d6c0b6edd08aa63fb1ab77415fd2` — copia en `config_efectiva.json`
- Versión de la herramienta: 0.1.0
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Banco Mundial — Indicators API pública y documentada (licencia CC BY 4.0)",
    "purpose": "Reto final académico: comparación del PIB en Norteamérica",
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
| Solicitudes/acciones | 2 | 3 |
| Páginas | 1 | 1 |
| Registros crudos | 30 | 50 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 2.11 | 60.0 |

## Calidad de datos

- Registros crudos: 30; exportados: 30
- Válidos: 30; con advertencias: 0; inválidos: 0
- Duplicados eliminados: 0; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| pais | 30 | 0 | 0 | 100% |
| codigo_pais | 30 | 0 | 0 | 100% |
| anio | 30 | 0 | 0 | 100% |
| pib_usd | 30 | 0 | 0 | 100% |

## Incidencias

- Ninguna

## Notas

- Perfil 'r03-worldbank-xml' actualizado como línea base.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs\r03-worldbank-xml\20261121T203238Z-0d985b\data.csv`
- json: `outputs\r03-worldbank-xml\20261121T203238Z-0d985b\data.json`
- excel: `outputs\r03-worldbank-xml\20261121T203238Z-0d985b\data.xlsx`
- sqlite: `outputs\web_extractor.sqlite`
- actions: `outputs\r03-worldbank-xml\20261121T203238Z-0d985b\actions.jsonl`
- log: `outputs\r03-worldbank-xml\20261121T203238Z-0d985b\run.log`
- profile: `outputs\r03-worldbank-xml\20261121T203238Z-0d985b\profile.json`
- config: `outputs\r03-worldbank-xml\20261121T203238Z-0d985b\config_efectiva.json`

## Siguientes pasos

- Validar muestras manualmente y documentar el resultado en la matriz de pruebas.
