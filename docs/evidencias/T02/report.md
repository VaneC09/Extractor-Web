# Informe de ejecución `20261110T225454Z-45c5da`

- Proyecto: **f02-tabla-html**
- URL objetivo: http://127.0.0.1:44555/static/tabla.html
- Método: `static_html`
- Estado: **completado** — Completado dentro de los límites
- Detalle: Extracción finalizada sin incidencias
- Inicio / fin (UTC): 2026-11-10T22:54:54Z / 2026-11-10T22:54:55Z
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Equipo del proyecto (propietario de los fixtures locales)",
    "purpose": "Pruebas académicas de extracción de tablas",
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
| Solicitudes/acciones | 2 | 4 |
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
| municipio | 6 | 0 | 0 | 100% |
| anio | 6 | 0 | 0 | 100% |
| poblacion | 5 | 1 | 1 | 83% |
| tasa_empleo | 5 | 1 | 0 | 83% |
| actualizado | 6 | 0 | 0 | 100% |

Muestra de errores de validación:

- #4 (http://127.0.0.1:44555/static/tabla.html): poblacion: 'cifra pendiente' no es un entero

## Incidencias

- Ninguna

## Notas

- Perfil 'f02-tabla-html' actualizado como línea base.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs/matrix/f02-tabla-html/20261110T225454Z-45c5da/data.csv`
- json: `outputs/matrix/f02-tabla-html/20261110T225454Z-45c5da/data.json`
- sqlite: `outputs/matrix/web_extractor.sqlite`
- actions: `outputs/matrix/f02-tabla-html/20261110T225454Z-45c5da/actions.jsonl`
- log: `outputs/matrix/f02-tabla-html/20261110T225454Z-45c5da/run.log`
- profile: `outputs/matrix/f02-tabla-html/20261110T225454Z-45c5da/profile.json`

## Siguientes pasos

- Validar muestras manualmente y documentar el resultado en la matriz de pruebas.
