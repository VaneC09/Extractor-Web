# Informe de ejecución `20261121T204050Z-63d9e2`

- Proyecto: **r05-dof-ejemplar-hoy**
- URL objetivo: https://dof.gob.mx/index.php
- Método: `static_html`
- Estado: **completado** — Completado dentro de los límites
- Detalle: Extracción finalizada sin incidencias
- Inicio / fin (UTC): 2026-11-21T20:40:50Z / 2026-11-21T20:40:54Z
- Configuración (SHA-256): `480f49eb4cb0dab964286be6760dfc987f69d1eccc9ec01498efc2bd82fc8046` — copia en `config_efectiva.json`
- Versión de la herramienta: 0.1.0
- Revisión humana requerida: no

## Autorización y alcance declarados

```json
{
  "authorization": {
    "confirmed": true,
    "authorized_by": "Diario Oficial de la Federación — publicación oficial de acceso público",
    "purpose": "Reto final académico: índice diario de publicaciones oficiales",
    "terms_reviewed": true,
    "environment": "production",
    "evidence_reference": "https://dof.gob.mx/robots.txt",
    "allow_authentication": false,
    "valid_until": null
  },
  "scope": {
    "allowed_domains": [
      "dof.gob.mx"
    ],
    "allowed_path_prefixes": [
      "/index.php"
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
| Solicitudes/acciones | 2 | 3 |
| Páginas | 1 | 1 |
| Registros crudos | 18 | 60 |
| Clics / scrolls | 0 / 0 | — |
| Tiempo (s) | 4.06 | 60.0 |

## Calidad de datos

- Registros crudos: 18; exportados: 18
- Válidos: 16; con advertencias: 2; inválidos: 0
- Duplicados eliminados: 0; inválidos descartados: 0

| Campo | Con valor | Vacíos | Errores | Tasa de llenado |
|---|---|---|---|---|
| titulo | 18 | 0 | 0 | 100% |
| url | 18 | 0 | 0 | 100% |
| fecha_publicacion | 16 | 2 | 2 | 89% |

Muestra de errores de validación:

- #16 (https://dof.gob.mx/index.php): fecha_publicacion: patrón 'fecha=(\\d{2}/\\d{2}/\\d{4})' no coincide con 'https://dof.gob.mx/busqueda_avanzada.php?cod_orga=AV&busqueda_cuerpo=C'
- #17 (https://dof.gob.mx/index.php): fecha_publicacion: patrón 'fecha=(\\d{2}/\\d{2}/\\d{4})' no coincide con 'https://dof.gob.mx/indicadores.php'

## Incidencias

- Ninguna

## Notas

- Perfil 'r05-dof-ejemplar-hoy' actualizado como línea base.

## Cambios frente al perfil anterior

- Sin cambios o sin perfil previo

## Archivos generados

- csv: `outputs\r05-dof-ejemplar-hoy\20261121T204050Z-63d9e2\data.csv`
- json: `outputs\r05-dof-ejemplar-hoy\20261121T204050Z-63d9e2\data.json`
- excel: `outputs\r05-dof-ejemplar-hoy\20261121T204050Z-63d9e2\data.xlsx`
- sqlite: `outputs\web_extractor.sqlite`
- actions: `outputs\r05-dof-ejemplar-hoy\20261121T204050Z-63d9e2\actions.jsonl`
- log: `outputs\r05-dof-ejemplar-hoy\20261121T204050Z-63d9e2\run.log`
- profile: `outputs\r05-dof-ejemplar-hoy\20261121T204050Z-63d9e2\profile.json`
- config: `outputs\r05-dof-ejemplar-hoy\20261121T204050Z-63d9e2\config_efectiva.json`

## Siguientes pasos

- Validar muestras manualmente y documentar el resultado en la matriz de pruebas.
