# Manual de usuario

## 1. Antes de empezar: autorización

Para un sitio que no sea el de pruebas, reúna y escriba en la sección `authorization`:

| Clave | Qué poner |
|---|---|
| `authorized_by` | Persona y organización propietaria que permite el acceso |
| `purpose` | Finalidad concreta del uso de los datos |
| `terms_reviewed` | `true` tras revisar términos de uso, licencia, políticas y robots.txt |
| `evidence_reference` | Referencia verificable del permiso (correo, contrato, ticket) — obligatoria en `production` |
| `valid_until` | Fecha de vencimiento del permiso, si existe |
| `allow_authentication` | `true` solo si el permiso cubre el acceso con una cuenta propia |
| `confirmed` | `true` cuando todo lo anterior es cierto |

Sin estos datos la herramienta solo valida la configuración, permite un diagnóstico pasivo si
indica `authorized_by`, y pruebas con archivos locales (`preview --from-file`).

## 2. Recorrido paso a paso

1. **Crear la configuración**: `python -m web_extractor init --url https://sitio/ruta --out mi.yaml`
   (asistente interactivo) o copie `examples/plantilla_sitio_autorizado.yaml`.
2. **Validar**: `python -m web_extractor validate mi.yaml`. Corrija cada línea `ruta.campo: mensaje`.
3. **Diagnosticar**: `python -m web_extractor diagnose mi.yaml [--render]`. Lea los indicios, la
   confianza y las limitaciones. Si aparece `[PARADA]`, no continúe: siga el paso legítimo indicado.
4. **Definir campos**: `python -m web_extractor suggest mi.yaml --out borrador.yaml` y revise el
   borrador, o escriba las reglas a mano (sección 3). Elija `extraction.method` explícitamente.
5. **Probar reglas sin solicitudes**: guarde una página permitida y ejecute
   `python -m web_extractor preview mi.yaml --from-file pagina.html`.
6. **Extraer**: `python -m web_extractor run mi.yaml`. Se muestra autorización, diagnóstico y vista
   previa; escriba `si` para confirmar. `--yes` equivale a esa confirmación explícita.
7. **Revisar resultados** en `outputs/<proyecto>/<run_id>/report.md` y los datos en CSV/JSON/SQLite.
   `config_efectiva.json` guarda la configuración exacta usada. Su huella SHA-256 aparece en cada
   registro (`_config_sha256`) y en el informe.
8. **Cancelar** en cualquier momento con `Ctrl+C` o creando `outputs/STOP` (bórrelo después).

### Con la interfaz gráfica

`python -m web_extractor gui` abre `http://127.0.0.1:8611`.

1. Escriba la URL y pulse **Comenzar**. Para practicar, active **Sitio de pruebas local** y elija
   un ejemplo en la barra lateral.
2. **Proyecto y autorización**: complete los datos del permiso. Abajo se listan en vivo los
   requisitos que faltan.
3. **Alcance y límites**: el dominio, las rutas y los topes. «Ajustar alcance a esta URL» los
   recalcula. Una variante `www.` es otro dominio: añádala solo si está autorizada.
4. **Diagnóstico**: en sitios reales pide confirmar la inspección. Muestra:
   - una tarjeta por método, con puntuación, confianza y requisitos;
   - las paradas, con el siguiente paso legítimo;
   - el botón **Aplicar sugerencia**, que copia las reglas propuestas, incluida la paginación.
5. **Campos y reglas**: tabla editable con selector, tipo, normalización y validación.
6. **Vista previa**: con un archivo local (0 solicitudes) o en vivo (1 página, solo con la
   autorización completa).
7. **Extracción**: marque la confirmación y pulse **Iniciar extracción**. Se ven contadores y
   acciones en vivo, y **Cancelar** detiene tras la acción en curso. Cada ejecución exige
   confirmar de nuevo.
8. **Resultados**: estado, calidad por campo, incidencias, cambios de estructura, descargas
   (CSV, JSON, informe, log) e historial del proyecto.
9. **Descargar configuración YAML** (barra lateral) la guarda para usarla con la CLI.

Qué ocurre con un sitio que no es de los ejemplos (sin permiso, redirecciones, robots.txt,
CAPTCHA, codificación): [sitios_no_incluidos.md](sitios_no_incluidos.md).

## 3. Reglas de campos

```yaml
extraction:
  method: static_html          # static_html | browser | structured_file | api
  record_selector: "article.producto"   # HTML: un elemento por registro
  # table_selector: "table#datos"       # alternativa para tablas (campos con column)
  # records_path: data.items            # JSON: ruta a la lista
  # file_format: csv                    # structured_file
  deduplicate_on: [codigo]
  drop_invalid: false
  keep_raw: true
  fields:
    - name: codigo
      attribute: data-id        # text (por defecto) | html | nombre de atributo
      required: true
      validate: {regex: "P-\\d+"}
    - name: precio
      selector: ".precio"       # CSS relativo al registro
      type: float               # string integer float boolean date datetime url
      normalize: [remove_currency, thousands_comma, empty_to_none]
      validate: {min: 0}
    - name: fecha
      selector: "time"
      attribute: datetime
      type: date
      date_format: "%d/%m/%Y"   # opcional; por defecto ISO 8601
    - name: cupo
      selector: ".cupo"
      pattern: "(\\d+)"         # conserva el grupo 1
      type: integer
```

Normalizadores: `strip`, `collapse_whitespace`, `lower`, `upper`, `title`, `strip_accents`,
`remove_currency`, `remove_percent`, `thousands_comma`, `decimal_comma`, `digits_only`, `empty_to_none`.

Orden de procesamiento por campo: normalizadores → `pattern` → tipo → validación. Un campo
obligatorio vacío o inválido marca el registro como `invalido`; uno opcional, como `advertencia`.

Paginación: `next_link` (+`next_selector`), `url_template` (+`url_template` con `{page}`; termina
en 404 o página vacía), `next_field` y `page_param` (solo API). Navegador: `wait_selector`,
`load_more_selector`, `infinite_scroll`, con topes `limits.max_clicks` y `limits.max_scrolls`.

Autenticación autorizada por formulario (`static_html`, `browser`, `structured_file` y `api`). Con
`browser`, el navegador abre `login_url`, localiza los campos por su atributo `name`, envía el
formulario una sola vez y continúa en la misma sesión. Ejemplo: `examples/f12_navegador_autenticado.yaml`.

```yaml
authorization: {allow_authentication: true, ...}
auth:
  type: form
  login_url: https://sitio/login
  username_env: MI_USUARIO      # nombres de variables, nunca valores
  password_env: MI_CLAVE
  failure_text: "Credenciales incorrectas"
```

Token o API key **emitido por el propietario y documentado** (solo `api` y `structured_file`).
Ejemplo: `examples/f13_api_con_token.yaml`.

```yaml
authorization: {allow_authentication: true, ...}
auth:
  type: header
  header_name: Authorization    # el que indique la documentación (p. ej. X-API-Key)
  header_prefix: "Bearer "      # vacío si la documentación no usa prefijo
  token_env: MI_API_TOKEN       # nombre de la variable, nunca el valor
```

Reglas del token:

- Se envía solo en solicitudes dentro del alcance; nunca a robots.txt.
- Se enmascara en logs e informes.
- Si falta la variable, la ejecución termina en `fallido` sin hacer solicitudes a la API.
- Si el servidor responde 401, la ejecución se detiene con `auth_required` y no se reintenta.
- `Cookie`, `Host` y `User-Agent` no se admiten como encabezado.

En la interfaz gráfica, la sección «Autenticación autorizada» de la pestaña «Campos y reglas»
ofrece las mismas tres opciones: sin autenticación, formulario y token.

## 4. Interpretar el estado final

| Estado | Significado | Qué hacer |
|---|---|---|
| `completado` | Terminó sin incidencias | Validar muestras |
| `completado_con_limites` | Un tope detuvo la ejecución | Ampliar solo si está autorizado |
| `parcial_barrera` / `detenido_barrera` | CAPTCHA, 429, 403, login, paywall… | No reintentar; pedir vía autorizada |
| `detenido_politica` | Fuera de alcance o robots.txt | Respetar; pedir permiso o ajustar alcance autorizado |
| `cancelado` | Ctrl+C o archivo STOP | Revisar antes de reanudar |
| `fallido` | Error técnico o login rechazado | Ver `run.log` y `report.md` |
| Revisión humana | Cambió la estructura frente al perfil | Revisar selectores; la línea base no se tocó |

## 5. Solución de errores comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Configuración inválida: ... Extra inputs are not permitted` | Clave desconocida o errata (o un secreto en el YAML) | Elimine la clave; las credenciales van en variables de entorno |
| `delay_seconds debe ser >= 1.0` | Pausa demasiado baja para un dominio remoto | Aumente la pausa |
| `Destino en red local/privada no admitido` | URL a localhost/IP privada | Solo para fixtures con `allow_private_network: true` |
| `Falta autorización o confirmación` | Sección `authorization` incompleta o `method: auto` | Complete los elementos listados y elija un método |
| `robots.txt no permite acceder` | Ruta prohibida por el sitio | No continuar por esa ruta |
| Vista previa sin registros | Selector incorrecto o contenido generado con JS | Use `diagnose --render`; pruebe `method: browser` o ajuste selectores con `--from-file` |
| Página sin registros (`empty_page`) durante `run` | Cambio de estructura | Revise selectores; compare perfiles con `compare-runs` |
| `No se pudo iniciar Chrome/ChromeDriver` | Chrome no instalado o sin acceso para descargar el driver | Instale Chrome; Selenium Manager necesita red la primera vez |
| `Faltan credenciales en las variables de entorno` | Variables no exportadas | `export MI_USUARIO=...` en la misma terminal |
| `El inicio de sesión autorizado fue rechazado` | Credenciales incorrectas o caducadas | Verifíquelas con el propietario; no se reintenta automáticamente |
| La ejecución se cancela sola | Existe `outputs/STOP` | Borre el archivo |
| `Se esperaba csv pero se recibió text/html` | La URL no apunta al archivo | Use el enlace directo al archivo autorizado |
