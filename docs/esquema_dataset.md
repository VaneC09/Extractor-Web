# Esquema del dataset de demostración

`examples/demo_dataset/` contiene la salida real de la ejecución T01 (catálogo ficticio de
papelería, 3 páginas) generada con `python -m web_extractor matrix`. Todos los valores son ficticios.

## Archivos

| Archivo | Contenido |
|---|---|
| `data.csv` | Una fila por registro exportado: campos procesados + columnas de linaje con prefijo `_` |
| `data.json` | Metadatos de la ejecución y, por registro, `data` (procesado), `raw` (original) y `lineage` |
| `summary.json` | Resumen: estado, consumo frente a límites, calidad, incidencias, cambios, salidas |
| `report.md` | Informe legible de la ejecución |
| `profile.json` | Perfil del sitio usado para detectar cambios en ejecuciones futuras |

## Campos de datos (T01)

| Campo | Tipo | Obligatorio | Origen (regla) | Normalización / validación |
|---|---|---|---|---|
| `sku` | string | sí | atributo `data-sku` de `article.product` | regex `SKU-\d{3}` |
| `nombre` | string | sí | texto de `.product-name` | `collapse_whitespace` |
| `precio` | float | no | texto de `.price` | `remove_currency`, `thousands_comma`, `empty_to_none`; 0 ≤ x ≤ 100000 |
| `disponible` | boolean | no | texto de `.stock` | Disponible → true, Agotado → false |
| `actualizado` | date (ISO) | no | atributo `datetime` de `time.updated` | ISO 8601 |
| `url_detalle` | url | no | `href` de `a.detail` (resuelto a absoluto) | http(s) absoluta |

## Columnas de linaje

| Columna CSV / clave JSON | Significado |
|---|---|
| `_record_id` / `record_id` | Hash SHA-256 (16 hex) de las claves de deduplicación |
| `_run_id` / `run_id` | Identificador de la ejecución (`AAAAMMDDTHHMMSSZ-xxxxxx`) |
| `_source_url` / `source_url` | URL exacta de la que se obtuvo el registro |
| `_retrieved_at` / `retrieved_at` | Fecha y hora UTC de la respuesta |
| `_method` / `method` | Método de adquisición |
| `_page_index` / `page_index` | Página (0 = primera) |
| `_validation_status` / `validation_status` | `valido`, `advertencia` o `invalido` |
| `_validation_errors` / `validation_errors` | Errores por campo |
| — / `transformations` | Pasos aplicados por campo, p. ej. `["remove_currency", "thousands_comma", "empty_to_none", "cast:float"]` |
| — / `position` | Posición del registro crudo antes de deduplicar |

## SQLite (`outputs/web_extractor.sqlite`)

- `runs(run_id, project, target_url, method, status, started_at, finished_at, metadata_json)`
- `records(run_id, position, record_id, validation_status, source_url, retrieved_at, data_json, raw_json, lineage_json)`
- `incidents(run_id, timestamp, kind, severity, url, message, next_step)`

Consulta de ejemplo:

```sql
SELECT json_extract(data_json, '$.nombre') AS nombre, json_extract(data_json, '$.precio') AS precio
FROM records WHERE validation_status = 'valido' ORDER BY precio DESC;
```

## Resultado de calidad de T01

11 registros crudos → 1 duplicado eliminado (`SKU-004` repetido en la página 3) → 10 exportados:
8 válidos, 1 con advertencia (precio "Consultar" no numérico) y 1 inválido (producto sin SKU, campo
obligatorio). El valor original siempre se conserva en `raw`.
