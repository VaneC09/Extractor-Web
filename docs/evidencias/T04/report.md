# Informe de ejecución `20261110T225456Z-1cc5da`

- Proyecto: **f04-cargar-mas**
- URL objetivo: http://127.0.0.1:44555/js/load-more.html
- Método: `browser`
- Estado: **completado_con_limites** — Completado parcialmente: se alcanzó un límite configurado
- Detalle: Límite alcanzado: max_clicks (2)
- Inicio / fin (UTC): 2026-11-10T22:54:56Z / 2026-11-10T22:54:58Z
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Equipo del proyecto (propietario de los fixtures locales)",
    "purpose": "Pruebas académicas de carga bajo demanda",
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
      "/js/"
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
| Solicitudes/acciones | 4 | 6 |
| Páginas | 1 | 1 |
| Registros crudos | 12 | 50 |
| Clics / scrolls | 2 / 0 | — |
| Tiempo (s) | 1.44 | 60.0 |

## Calidad de datos

- Registros crudos: 12; exportados: 12
- Válidos: 12; con advertencias: 0; inválidos: 0
- Duplicados eliminados: 0; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| codigo | 12 | 0 | 0 | 100% |
| nombre | 12 | 0 | 0 | 100% |
| lugares | 12 | 0 | 0 | 100% |
| sede | 12 | 0 | 0 | 100% |

## Incidencias

- **limit** (baja) Límite alcanzado: max_clicks (2) — http://127.0.0.1:44555/js/load-more.html — Siguiente paso: Ampliar límites solo dentro de lo autorizado.

## Notas

- Se alcanzó max_clicks con el botón aún activo: puede haber más contenido sin cargar
- Perfil 'f04-cargar-mas' actualizado como línea base.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs/matrix/f04-cargar-mas/20261110T225456Z-1cc5da/data.csv`
- json: `outputs/matrix/f04-cargar-mas/20261110T225456Z-1cc5da/data.json`
- sqlite: `outputs/matrix/web_extractor.sqlite`
- actions: `outputs/matrix/f04-cargar-mas/20261110T225456Z-1cc5da/actions.jsonl`
- log: `outputs/matrix/f04-cargar-mas/20261110T225456Z-1cc5da/run.log`
- profile: `outputs/matrix/f04-cargar-mas/20261110T225456Z-1cc5da/profile.json`

## Siguientes pasos

- Ampliar límites solo dentro de lo autorizado.
- Si necesita más datos, amplíe límites solo dentro de lo autorizado y con pausas adecuadas.
