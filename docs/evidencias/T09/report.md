# Informe de ejecución `20261110T225502Z-bf5cc9`

- Proyecto: **f09-barrera-captcha**
- URL objetivo: http://127.0.0.1:44555/barrier/captcha.html
- Método: `static_html`
- Estado: **detenido_barrera** — Detenido por una barrera antes de obtener datos
- Detalle: Barrera detectada (captcha): Indicios de CAPTCHA en la página
- Inicio / fin (UTC): 2026-11-10T22:55:02Z / 2026-11-10T22:55:02Z
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Equipo del proyecto (propietario de los fixtures locales)",
    "purpose": "Comprobar la parada segura ante CAPTCHA",
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

- **captcha** (alta) Indicios de CAPTCHA en la página — evidencia: requerida</title> </head> <body> <h1>Verifica que eres humano</h1> <p>Para continuar, completa la v — http://127.0.0.1:44555/barrier/captcha.html — Siguiente paso: Solicitar al propietario del sitio una vía autorizada (API, exportación o permiso explícito). No resolver ni evadir el CAPTCHA.

## Notas

- La línea base del perfil no se actualizó porque la ejecución no terminó correctamente.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs/matrix/f09-barrera-captcha/20261110T225502Z-bf5cc9/data.csv`
- json: `outputs/matrix/f09-barrera-captcha/20261110T225502Z-bf5cc9/data.json`
- sqlite: `outputs/matrix/web_extractor.sqlite`
- actions: `outputs/matrix/f09-barrera-captcha/20261110T225502Z-bf5cc9/actions.jsonl`
- log: `outputs/matrix/f09-barrera-captcha/20261110T225502Z-bf5cc9/run.log`
- profile: `outputs/matrix/f09-barrera-captcha/20261110T225502Z-bf5cc9/profile.json`

## Siguientes pasos

- Solicitar al propietario del sitio una vía autorizada (API, exportación o permiso explícito). No resolver ni evadir el CAPTCHA.
