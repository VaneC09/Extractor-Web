# Informe de ejecución `20261110T225506Z-34a7b6`

- Proyecto: **f01-catalogo-estatico**
- URL objetivo: http://127.0.0.1:44555/static/catalogo?page=1
- Método: `static_html`
- Estado: **completado** — Completado dentro de los límites
- Detalle: Extracción finalizada sin incidencias
- Inicio / fin (UTC): 2026-11-10T22:55:06Z / 2026-11-10T22:55:06Z
- Revisión humana requerida: sí

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
| Solicitudes/acciones | 4 | 10 |
| Páginas | 3 | 5 |
| Registros crudos | 11 | 50 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 0.61 | 60.0 |

## Calidad de datos

- Registros crudos: 11; exportados: 10
- Válidos: 0; con advertencias: 9; inválidos: 1
- Duplicados eliminados: 1; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| sku | 10 | 1 | 0 | 91% |
| nombre | 11 | 0 | 0 | 100% |
| precio | 0 | 11 | 0 | 0% |
| disponible | 11 | 0 | 0 | 100% |
| actualizado | 11 | 0 | 0 | 100% |
| url_detalle | 11 | 0 | 0 | 100% |

Muestra de errores de validación:

- #9 (http://127.0.0.1:44555/static/catalogo?page=3): sku: obligatorio y vacío

## Incidencias

- **change_detected** (alta) Cambios relevantes frente al perfil anterior; no se corrige nada automáticamente — http://127.0.0.1:44555/static/catalogo?page=1 — Siguiente paso: Revisión humana de selectores y alcance.

## Notas

- La línea base del perfil NO se actualizó por requerir revisión humana.

## Cambios frente al perfil anterior

- [media] rule_changed: precio.selector: '.price' -> '.precio-rediseñado'
- [alta] fill_rate_drop: precio: tasa de llenado 91% -> 0% (posible selector roto o cambio de estructura)

## Archivos generados

- csv: `outputs/matrix/f01-catalogo-estatico/20261110T225506Z-34a7b6/data.csv`
- json: `outputs/matrix/f01-catalogo-estatico/20261110T225506Z-34a7b6/data.json`
- sqlite: `outputs/matrix/web_extractor.sqlite`
- actions: `outputs/matrix/f01-catalogo-estatico/20261110T225506Z-34a7b6/actions.jsonl`
- log: `outputs/matrix/f01-catalogo-estatico/20261110T225506Z-34a7b6/run.log`
- profile: `outputs/matrix/f01-catalogo-estatico/20261110T225506Z-34a7b6/profile.json`

## Siguientes pasos

- Revisión humana de selectores y alcance.
- Revise los cambios detectados frente al perfil anterior antes de volver a ejecutar; no se actualizó la línea base.
- Revise los registros inválidos (columna _validation_errors) y ajuste reglas o selectores.
