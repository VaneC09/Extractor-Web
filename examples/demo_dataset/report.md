# Informe de ejecución `20261110T225454Z-4370cb`

- Proyecto: **f01-catalogo-estatico**
- URL objetivo: http://127.0.0.1:44555/static/catalogo?page=1
- Método: `static_html`
- Estado: **completado** — Completado dentro de los límites
- Detalle: Extracción finalizada sin incidencias
- Inicio / fin (UTC): 2026-11-10T22:54:54Z / 2026-11-10T22:54:54Z
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
| Solicitudes/acciones | 4 | 10 |
| Páginas | 3 | 5 |
| Registros crudos | 11 | 50 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 0.61 | 60.0 |

## Calidad de datos

- Registros crudos: 11; exportados: 10
- Válidos: 8; con advertencias: 1; inválidos: 1
- Duplicados eliminados: 1; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| sku | 10 | 1 | 0 | 91% |
| nombre | 11 | 0 | 0 | 100% |
| precio | 10 | 1 | 1 | 91% |
| disponible | 11 | 0 | 0 | 100% |
| actualizado | 11 | 0 | 0 | 100% |
| url_detalle | 11 | 0 | 0 | 100% |

Muestra de errores de validación:

- #5 (http://127.0.0.1:44555/static/catalogo?page=2): precio: 'Consultar' no es un número
- #9 (http://127.0.0.1:44555/static/catalogo?page=3): sku: obligatorio y vacío

## Incidencias

- Ninguna

## Notas

- Perfil 'f01-catalogo-estatico' actualizado como línea base.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs/matrix/f01-catalogo-estatico/20261110T225454Z-4370cb/data.csv`
- json: `outputs/matrix/f01-catalogo-estatico/20261110T225454Z-4370cb/data.json`
- sqlite: `outputs/matrix/web_extractor.sqlite`
- actions: `outputs/matrix/f01-catalogo-estatico/20261110T225454Z-4370cb/actions.jsonl`
- log: `outputs/matrix/f01-catalogo-estatico/20261110T225454Z-4370cb/run.log`
- profile: `outputs/matrix/f01-catalogo-estatico/20261110T225454Z-4370cb/profile.json`

## Siguientes pasos

- Revise los registros inválidos (columna _validation_errors) y ajuste reglas o selectores.
