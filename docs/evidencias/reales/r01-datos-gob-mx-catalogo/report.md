# Informe de ejecución `20261121T203738Z-989d99`

- Proyecto: **r01-datos-gob-mx-catalogo**
- URL objetivo: https://www.datos.gob.mx/dataset/?page=1
- Método: `static_html`
- Estado: **completado_con_limites** — Completado parcialmente: se alcanzó un límite configurado
- Detalle: Límite alcanzado: max_records (40)
- Inicio / fin (UTC): 2026-11-21T20:37:38Z / 2026-11-21T20:37:59Z
- Configuración (SHA-256): `7493d6f317365963fe3674813a433bb30a3fd910ff2b84eff518b7a832decd9e` — copia en `config_efectiva.json`
- Versión de la herramienta: 0.1.0
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Plataforma Nacional de Datos Abiertos (datos públicos de libre uso); URL indicada por el docente",
    "purpose": "Reto final académico: catálogo de conjuntos de datos abiertos, sin datos personales",
    "terms_reviewed": true,
    "environment": "production",
    "evidence_reference": "https://www.datos.gob.mx/ (datos abiertos) y https://www.datos.gob.mx/robots.txt",
    "allow_authentication": false,
    "valid_until": null
  },
  "scope": {
    "allowed_domains": [
      "www.datos.gob.mx"
    ],
    "allowed_path_prefixes": [
      "/dataset/"
    ],
    "allowed_schemes": [
      "https"
    ],
    "allow_private_network": false,
    "respect_robots_txt": true
  }
}
```

## Consumo frente a límites

| Recurso | Usado | Límite |
|---|---|---|
| Solicitudes/acciones | 3 | 4 |
| Páginas | 2 | 2 |
| Registros crudos | 40 | 40 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 20.94 | 120.0 |

## Calidad de datos

- Registros crudos: 40; exportados: 40
- Válidos: 40; con advertencias: 0; inválidos: 0
- Duplicados eliminados: 0; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| titulo | 40 | 0 | 0 | 100% |
| url | 40 | 0 | 0 | 100% |
| institucion | 40 | 0 | 0 | 100% |
| actualizacion | 40 | 0 | 0 | 100% |

## Incidencias

- **limit** (baja) Límite alcanzado: max_records (40) — https://www.datos.gob.mx/dataset/?page=1 — Siguiente paso: Ampliar límites solo dentro de lo autorizado.

## Notas

- Perfil 'r01-datos-gob-mx-catalogo' actualizado como línea base.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs\r01-datos-gob-mx-catalogo\20261121T203738Z-989d99\data.csv`
- json: `outputs\r01-datos-gob-mx-catalogo\20261121T203738Z-989d99\data.json`
- excel: `outputs\r01-datos-gob-mx-catalogo\20261121T203738Z-989d99\data.xlsx`
- sqlite: `outputs\web_extractor.sqlite`
- actions: `outputs\r01-datos-gob-mx-catalogo\20261121T203738Z-989d99\actions.jsonl`
- log: `outputs\r01-datos-gob-mx-catalogo\20261121T203738Z-989d99\run.log`
- profile: `outputs\r01-datos-gob-mx-catalogo\20261121T203738Z-989d99\profile.json`
- config: `outputs\r01-datos-gob-mx-catalogo\20261121T203738Z-989d99\config_efectiva.json`

## Siguientes pasos

- Ampliar límites solo dentro de lo autorizado.
- Si necesita más datos, amplíe límites solo dentro de lo autorizado y con pausas adecuadas.
