# Informe de ejecución `20261110T225500Z-fdfcbd`

- Proyecto: **f06-api-documentada**
- URL objetivo: http://127.0.0.1:44555/api/v1/products
- Método: `api`
- Estado: **completado** — Completado dentro de los límites
- Detalle: Extracción finalizada sin incidencias
- Inicio / fin (UTC): 2026-11-10T22:55:00Z / 2026-11-10T22:55:00Z
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Equipo del proyecto (propietario de los fixtures locales)",
    "purpose": "Pruebas académicas de consumo de API documentada",
    "terms_reviewed": true,
    "environment": "fixture",
    "evidence_reference": null,
    "allow_authentication": false,
    "valid_until": null
  },
  "scope": {
    "allowed_domains": [
      "127.0.0.1",
      "localhost"
    ],
    "allowed_path_prefixes": [
      "/api/"
    ],
    "allowed_schemes": [
      "http"
    ],
    "allow_private_network": true,
    "respect_robots_txt": true
  }
}
```

## Consumo frente a límites

| Recurso | Usado | Límite |
|---|---|---|
| Solicitudes/acciones | 4 | 8 |
| Páginas | 3 | 5 |
| Registros crudos | 9 | 100 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 0.6 | 30.0 |

## Calidad de datos

- Registros crudos: 9; exportados: 9
- Válidos: 9; con advertencias: 0; inválidos: 0
- Duplicados eliminados: 0; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| id | 9 | 0 | 0 | 100% |
| nombre | 9 | 0 | 0 | 100% |
| precio | 9 | 0 | 0 | 100% |
| moneda | 9 | 0 | 0 | 100% |
| categoria | 9 | 0 | 0 | 100% |
| activo | 9 | 0 | 0 | 100% |

## Incidencias

- Ninguna

## Notas

- Perfil 'f06-api-documentada' actualizado como línea base.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs/matrix/f06-api-documentada/20261110T225500Z-fdfcbd/data.csv`
- json: `outputs/matrix/f06-api-documentada/20261110T225500Z-fdfcbd/data.json`
- sqlite: `outputs/matrix/web_extractor.sqlite`
- actions: `outputs/matrix/f06-api-documentada/20261110T225500Z-fdfcbd/actions.jsonl`
- log: `outputs/matrix/f06-api-documentada/20261110T225500Z-fdfcbd/run.log`
- profile: `outputs/matrix/f06-api-documentada/20261110T225500Z-fdfcbd/profile.json`

## Siguientes pasos

- Validar muestras manualmente y documentar el resultado en la matriz de pruebas.
