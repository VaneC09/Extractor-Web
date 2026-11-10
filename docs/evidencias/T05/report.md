# Informe de ejecución `20261110T225458Z-93a539`

- Proyecto: **f05-scroll-infinito**
- URL objetivo: http://127.0.0.1:44555/js/scroll.html
- Método: `browser`
- Estado: **completado_con_limites** — Completado parcialmente: se alcanzó un límite configurado
- Detalle: Límite alcanzado: max_scrolls (2)
- Inicio / fin (UTC): 2026-11-10T22:54:58Z / 2026-11-10T22:55:00Z
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Equipo del proyecto (propietario de los fixtures locales)",
    "purpose": "Pruebas académicas de scroll infinito acotado",
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
| Registros crudos | 15 | 50 |
| Clics / scrolls | 0 / 2 | — |
| Tiempo (s) | 1.53 | 60.0 |

## Calidad de datos

- Registros crudos: 15; exportados: 15
- Válidos: 15; con advertencias: 0; inválidos: 0
- Duplicados eliminados: 0; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| titulo | 15 | 0 | 0 | 100% |
| autor | 15 | 0 | 0 | 100% |
| anio | 15 | 0 | 0 | 100% |

## Incidencias

- **limit** (baja) Límite alcanzado: max_scrolls (2) — http://127.0.0.1:44555/js/scroll.html — Siguiente paso: Ampliar límites solo dentro de lo autorizado.

## Notas

- Se alcanzó max_scrolls: puede haber más contenido sin cargar
- Perfil 'f05-scroll-infinito' actualizado como línea base.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs/matrix/f05-scroll-infinito/20261110T225458Z-93a539/data.csv`
- json: `outputs/matrix/f05-scroll-infinito/20261110T225458Z-93a539/data.json`
- sqlite: `outputs/matrix/web_extractor.sqlite`
- actions: `outputs/matrix/f05-scroll-infinito/20261110T225458Z-93a539/actions.jsonl`
- log: `outputs/matrix/f05-scroll-infinito/20261110T225458Z-93a539/run.log`
- profile: `outputs/matrix/f05-scroll-infinito/20261110T225458Z-93a539/profile.json`

## Siguientes pasos

- Ampliar límites solo dentro de lo autorizado.
- Si necesita más datos, amplíe límites solo dentro de lo autorizado y con pausas adecuadas.
