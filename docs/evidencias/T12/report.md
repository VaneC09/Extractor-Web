# Informe de ejecución `20261110T225504Z-b3de10`

- Proyecto: **t12-cancelacion**
- URL objetivo: http://127.0.0.1:44555/static/catalogo?page=1
- Método: `static_html`
- Estado: **cancelado** — Cancelado por el usuario
- Detalle: Ejecución cancelada: cancelación de prueba
- Inicio / fin (UTC): 2026-11-10T22:55:04Z / 2026-11-10T22:55:05Z
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Equipo del proyecto (propietario de los fixtures locales)",
    "purpose": "Pruebas académicas de la herramienta con datos ficticios",
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
      "/static/"
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
| Solicitudes/acciones | 3 | 10 |
| Páginas | 2 | 5 |
| Registros crudos | 4 | 50 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 1.5 | 60.0 |

## Calidad de datos

- Registros crudos: 4; exportados: 4
- Válidos: 4; con advertencias: 0; inválidos: 0
- Duplicados eliminados: 0; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| sku | 4 | 0 | 0 | 100% |
| nombre | 4 | 0 | 0 | 100% |
| precio | 4 | 0 | 0 | 100% |
| disponible | 4 | 0 | 0 | 100% |
| actualizado | 4 | 0 | 0 | 100% |
| url_detalle | 4 | 0 | 0 | 100% |

## Incidencias

- **cancelled** (media) Ejecución cancelada: cancelación de prueba — http://127.0.0.1:44555/static/catalogo?page=1 — Siguiente paso: Reanudar solo tras revisión humana.

## Notas

- La línea base del perfil no se actualizó porque la ejecución no terminó correctamente.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs/matrix/t12-cancelacion/20261110T225504Z-b3de10/data.csv`
- json: `outputs/matrix/t12-cancelacion/20261110T225504Z-b3de10/data.json`
- sqlite: `outputs/matrix/web_extractor.sqlite`
- actions: `outputs/matrix/t12-cancelacion/20261110T225504Z-b3de10/actions.jsonl`
- log: `outputs/matrix/t12-cancelacion/20261110T225504Z-b3de10/run.log`
- profile: `outputs/matrix/t12-cancelacion/20261110T225504Z-b3de10/profile.json`

## Siguientes pasos

- Reanudar solo tras revisión humana.
