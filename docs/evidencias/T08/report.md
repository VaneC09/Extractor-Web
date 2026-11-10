# Informe de ejecución `20261110T225501Z-08bf39`

- Proyecto: **f08-autenticacion**
- URL objetivo: http://127.0.0.1:44555/auth/privado
- Método: `static_html`
- Estado: **completado** — Completado dentro de los límites
- Detalle: Extracción finalizada sin incidencias
- Inicio / fin (UTC): 2026-11-10T22:55:01Z / 2026-11-10T22:55:02Z
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Equipo del proyecto (propietario del entorno de prueba)",
    "purpose": "Validar el flujo de autenticación autorizada sin datos reales",
    "terms_reviewed": true,
    "environment": "fixture",
    "evidence_reference": null,
    "allow_authentication": true,
    "valid_until": null
  },
  "scope": {
    "allowed_domains": [
      "127.0.0.1",
      "localhost"
    ],
    "allowed_path_prefixes": [
      "/auth/"
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
| Solicitudes/acciones | 5 | 8 |
| Páginas | 1 | 1 |
| Registros crudos | 5 | 20 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 0.8 | 30.0 |

## Calidad de datos

- Registros crudos: 5; exportados: 5
- Válidos: 5; con advertencias: 0; inválidos: 0
- Duplicados eliminados: 0; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| folio | 5 | 0 | 0 | 100% |
| titulo | 5 | 0 | 0 | 100% |
| estado | 5 | 0 | 0 | 100% |

## Incidencias

- Ninguna

## Notas

- Perfil 'f08-autenticacion' actualizado como línea base.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs/matrix/f08-autenticacion/20261110T225501Z-08bf39/data.csv`
- json: `outputs/matrix/f08-autenticacion/20261110T225501Z-08bf39/data.json`
- sqlite: `outputs/matrix/web_extractor.sqlite`
- actions: `outputs/matrix/f08-autenticacion/20261110T225501Z-08bf39/actions.jsonl`
- log: `outputs/matrix/f08-autenticacion/20261110T225501Z-08bf39/run.log`
- profile: `outputs/matrix/f08-autenticacion/20261110T225501Z-08bf39/profile.json`

## Siguientes pasos

- Validar muestras manualmente y documentar el resultado en la matriz de pruebas.
