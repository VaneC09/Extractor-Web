# Informe de ejecución `20261121T203842Z-f28df9`

- Proyecto: **r04-data-gov-navegador**
- URL objetivo: https://catalog.data.gov/
- Método: `browser`
- Estado: **completado** — Completado dentro de los límites
- Detalle: Extracción finalizada sin incidencias
- Inicio / fin (UTC): 2026-11-21T20:38:42Z / 2026-11-21T20:38:58Z
- Configuración (SHA-256): `f69cf036aec62bfd19dc5258c9f729767dad4e67954c7523ef3a46852bf6bb01` — copia en `config_efectiva.json`
- Versión de la herramienta: 0.1.0
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Data.gov — catálogo público del Gobierno de EE. UU.",
    "purpose": "Reto final académico: inventario de conjuntos de datos y formatos publicados",
    "terms_reviewed": true,
    "environment": "production",
    "evidence_reference": "https://catalog.data.gov/robots.txt",
    "allow_authentication": false,
    "valid_until": null
  },
  "scope": {
    "allowed_domains": [
      "catalog.data.gov"
    ],
    "allowed_path_prefixes": [
      "/"
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
| Registros crudos | 20 | 30 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 15.72 | 90.0 |

## Calidad de datos

- Registros crudos: 20; exportados: 20
- Válidos: 19; con advertencias: 1; inválidos: 0
- Duplicados eliminados: 0; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| titulo | 20 | 0 | 0 | 100% |
| url | 20 | 0 | 0 | 100% |
| organizacion | 20 | 0 | 0 | 100% |
| actualizado | 19 | 1 | 0 | 95% |
| formatos | 20 | 0 | 0 | 100% |

## Incidencias

- Ninguna

## Notas

- Perfil 'r04-data-gov-navegador' actualizado como línea base.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs\r04-data-gov-navegador\20261121T203842Z-f28df9\data.csv`
- json: `outputs\r04-data-gov-navegador\20261121T203842Z-f28df9\data.json`
- excel: `outputs\r04-data-gov-navegador\20261121T203842Z-f28df9\data.xlsx`
- sqlite: `outputs\web_extractor.sqlite`
- actions: `outputs\r04-data-gov-navegador\20261121T203842Z-f28df9\actions.jsonl`
- log: `outputs\r04-data-gov-navegador\20261121T203842Z-f28df9\run.log`
- profile: `outputs\r04-data-gov-navegador\20261121T203842Z-f28df9\profile.json`
- config: `outputs\r04-data-gov-navegador\20261121T203842Z-f28df9\config_efectiva.json`

## Siguientes pasos

- Validar muestras manualmente y documentar el resultado en la matriz de pruebas.
