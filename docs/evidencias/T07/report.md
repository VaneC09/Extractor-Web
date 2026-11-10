# Informe de ejecución `20261110T225501Z-172ea3`

- Proyecto: **f07-archivo-csv**
- URL objetivo: http://127.0.0.1:44555/files/estaciones.csv
- Método: `structured_file`
- Estado: **completado** — Completado dentro de los límites
- Detalle: Extracción finalizada sin incidencias
- Inicio / fin (UTC): 2026-11-10T22:55:01Z / 2026-11-10T22:55:01Z
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Equipo del proyecto (propietario de los fixtures locales)",
    "purpose": "Pruebas académicas de archivos estructurados",
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
      "/files/"
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
| Solicitudes/acciones | 2 | 3 |
| Páginas | 1 | 1 |
| Registros crudos | 6 | 100 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 0.21 | 30.0 |

## Calidad de datos

- Registros crudos: 6; exportados: 5
- Válidos: 3; con advertencias: 2; inválidos: 0
- Duplicados eliminados: 1; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| id_estacion | 6 | 0 | 0 | 100% |
| nombre | 6 | 0 | 0 | 100% |
| municipio | 6 | 0 | 0 | 100% |
| latitud | 5 | 1 | 1 | 83% |
| longitud | 6 | 0 | 0 | 100% |
| activa | 6 | 0 | 0 | 100% |
| ultima_lectura | 5 | 1 | 1 | 83% |

Muestra de errores de validación:

- #3 (http://127.0.0.1:44555/files/estaciones.csv): latitud: 'abc' no es un número
- #4 (http://127.0.0.1:44555/files/estaciones.csv): ultima_lectura: 'fecha desconocida' no es una fecha válida (ISO 8601)

## Incidencias

- Ninguna

## Notas

- Perfil 'f07-archivo-csv' actualizado como línea base.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs/matrix/f07-archivo-csv/20261110T225501Z-172ea3/data.csv`
- json: `outputs/matrix/f07-archivo-csv/20261110T225501Z-172ea3/data.json`
- sqlite: `outputs/matrix/web_extractor.sqlite`
- actions: `outputs/matrix/f07-archivo-csv/20261110T225501Z-172ea3/actions.jsonl`
- log: `outputs/matrix/f07-archivo-csv/20261110T225501Z-172ea3/run.log`
- profile: `outputs/matrix/f07-archivo-csv/20261110T225501Z-172ea3/profile.json`

## Siguientes pasos

- Validar muestras manualmente y documentar el resultado en la matriz de pruebas.
