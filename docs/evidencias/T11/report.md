# Informe de ejecución `20261110T225503Z-5e0992`

- Proyecto: **f11-robots-prohibido**
- URL objetivo: http://127.0.0.1:44555/privado/datos.html
- Método: `static_html`
- Estado: **detenido_politica** — Detenido por política (alcance, robots.txt o autorización)
- Detalle: robots.txt no permite acceder a http://127.0.0.1:44555/privado/datos.html
- Inicio / fin (UTC): 2026-11-10T22:55:03Z / 2026-11-10T22:55:03Z
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Equipo del proyecto (propietario de los fixtures locales)",
    "purpose": "Comprobar el respeto a robots.txt",
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
      "/privado/"
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
| Solicitudes/acciones | 1 | 3 |
| Páginas | 1 | 1 |
| Registros crudos | 0 | 10 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 0.0 | 30.0 |

## Calidad de datos

- Registros crudos: 0; exportados: 0
- Válidos: 0; con advertencias: 0; inválidos: 0
- Duplicados eliminados: 0; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| texto | 0 | 0 | 0 | 0% |

## Incidencias

- **robots_disallow** (alta) robots.txt no permite acceder a http://127.0.0.1:44555/privado/datos.html — http://127.0.0.1:44555/privado/datos.html — Siguiente paso: Respetar robots.txt; solicitar permiso explícito o una vía alternativa autorizada.

## Notas

- La línea base del perfil no se actualizó porque la ejecución no terminó correctamente.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs/matrix/f11-robots-prohibido/20261110T225503Z-5e0992/data.csv`
- json: `outputs/matrix/f11-robots-prohibido/20261110T225503Z-5e0992/data.json`
- sqlite: `outputs/matrix/web_extractor.sqlite`
- actions: `outputs/matrix/f11-robots-prohibido/20261110T225503Z-5e0992/actions.jsonl`
- log: `outputs/matrix/f11-robots-prohibido/20261110T225503Z-5e0992/run.log`
- profile: `outputs/matrix/f11-robots-prohibido/20261110T225503Z-5e0992/profile.json`

## Siguientes pasos

- Respetar robots.txt; solicitar permiso explícito o una vía alternativa autorizada.
