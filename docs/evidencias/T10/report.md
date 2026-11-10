# Informe de ejecución `20261110T225503Z-88096c`

- Proyecto: **f10-limite-tasa**
- URL objetivo: http://127.0.0.1:44555/barrier/limite
- Método: `static_html`
- Estado: **detenido_barrera** — Detenido por una barrera antes de obtener datos
- Detalle: Barrera detectada (rate_limit): HTTP 429: límite de solicitudes
- Inicio / fin (UTC): 2026-11-10T22:55:03Z / 2026-11-10T22:55:03Z
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Equipo del proyecto (propietario de los fixtures locales)",
    "purpose": "Comprobar la parada segura ante límites de tasa",
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
      "/barrier/"
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
| Solicitudes/acciones | 2 | 5 |
| Páginas | 1 | 3 |
| Registros crudos | 0 | 10 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 0.2 | 30.0 |

## Calidad de datos

- Registros crudos: 0; exportados: 0
- Válidos: 0; con advertencias: 0; inválidos: 0
- Duplicados eliminados: 0; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| texto | 0 | 0 | 0 | 0% |

## Incidencias

- **rate_limit** (alta) HTTP 429: límite de solicitudes — evidencia: Retry-After=120 — http://127.0.0.1:44555/barrier/limite — Siguiente paso: Detener y reducir frecuencia; consultar con el propietario los límites admitidos antes de volver a intentar en otro momento.

## Notas

- La línea base del perfil no se actualizó porque la ejecución no terminó correctamente.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs/matrix/f10-limite-tasa/20261110T225503Z-88096c/data.csv`
- json: `outputs/matrix/f10-limite-tasa/20261110T225503Z-88096c/data.json`
- sqlite: `outputs/matrix/web_extractor.sqlite`
- actions: `outputs/matrix/f10-limite-tasa/20261110T225503Z-88096c/actions.jsonl`
- log: `outputs/matrix/f10-limite-tasa/20261110T225503Z-88096c/run.log`
- profile: `outputs/matrix/f10-limite-tasa/20261110T225503Z-88096c/profile.json`

## Siguientes pasos

- Detener y reducir frecuencia; consultar con el propietario los límites admitidos antes de volver a intentar en otro momento.
