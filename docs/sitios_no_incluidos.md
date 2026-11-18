# ¿Qué pasa con un sitio que no es uno de los ejemplos?

Los ejemplos de `examples/` son solo escenarios de práctica. El motor no depende de ellos: con
cualquier URL se crea una configuración conservadora (`init` o el botón **Comenzar** de la
interfaz gráfica) y el flujo es siempre el mismo. Este documento describe qué ocurre en cada paso,
qué se validó y qué no.

## Resumen

1. **Sin autorización declarada, no se hace ninguna solicitud** al sitio. Solo se valida la
   configuración.
2. **Con alguien que autoriza la inspección** (`authorized_by`), se permite un diagnóstico pasivo de
   hasta 3 solicitudes: robots.txt, el documento y una redirección.
3. **La extracción exige la autorización completa**: confirmación, finalidad, términos revisados,
   referencia del permiso en sitios reales y un método explícito. Además, cada ejecución se
   confirma por separado.
4. Ante robots.txt prohibitivo, redirección fuera del alcance, CAPTCHA, desafío anti-bot, 401/403,
   429 o 503, **se detiene** sin reintentar. Registra una incidencia con el siguiente paso legítimo.
5. Si el diagnóstico no encuentra una estructura clara, las reglas se escriben a mano. Se prueban
   con la vista previa sobre un HTML guardado localmente, sin solicitudes.

## Paso a paso

| Paso | Qué hace la herramienta | Solicitudes | Si algo falla |
|---|---|---|---|
| 1. URL nueva | Crea la configuración: `confirmed: false`, alcance = host exacto y carpeta de la URL, método `auto`, pausa 3 s (0,5 s en local), 5 solicitudes, 2 páginas, 50 registros | 0 | URL no http(s), con credenciales o hacia red privada: error de configuración |
| 2. Autorización | Muestra en vivo qué falta (casilla por casilla en la interfaz) | 0 | Diagnóstico y extracción bloqueados con la lista exacta de requisitos |
| 3. Diagnóstico | robots.txt → documento → inspección del HTML → método sugerido con confianza | ≤ 3 (+1 con navegador) | Ver la tabla de situaciones |
| 4. Reglas | Sugiere un selector de registro, campos y paginación, siempre como borrador | 0 | Si no hay estructura repetida, sugiere un único campo `texto`; las reglas se escriben a mano |
| 5. Vista previa | Una página con el adaptador real, o un archivo local | ≤ 2, o 0 con archivo | Sin registros: revisar selectores o probar el método Navegador |
| 6. Extracción | Topes de solicitudes, páginas, registros, tiempo, clics y scrolls; cancelación inmediata | dentro de `limits` | Estado final con motivo, incidencias y siguientes pasos |
| 7. Resultados | CSV/JSON/SQLite, informe, perfil y comparación con la ejecución anterior | 0 | Cambio de estructura → revisión humana, sin actualizar la línea base |

## Situaciones típicas de un sitio real

| Situación | Qué hace | Estado / incidencia | Paso legítimo que se sugiere | Validado con |
|---|---|---|---|---|
| Sin autorización | No hace ninguna solicitud | `AuthorizationError` (código 3) | Completar la autorización | Sesión simulada: 0 solicitudes |
| Solo `authorized_by` | Diagnostica; la extracción sigue bloqueada | Falta `evidence_reference`, `confirmed`… | Completar el permiso | Sesión simulada |
| `ejemplo.org` → `www.ejemplo.org` | No sigue la redirección | `out_of_scope` o `robots_disallow` con «redirige a…» | Añadir la variante solo si el propietario la autoriza | Sesión simulada + fixture local (T18) |
| robots.txt 404 | Permite el acceso (RFC 9309) | — | — | Sesión simulada |
| robots.txt 5xx o sin respuesta | Asume prohibición total | `robots_disallow` «estado 500» | Reintentar más tarde o pedir permiso | Sesión simulada |
| robots.txt prohíbe la ruta | No solicita la ruta | `detenido_politica` | Pedir permiso o una vía alternativa | Fixture local (T11) |
| 403 con «Just a moment… / cf-chl» | Se detiene después de 1 solicitud | `bot_challenge` | Pedir acceso autorizado; no evadir | Sesión simulada + fixture local |
| CAPTCHA (reCAPTCHA, hCaptcha, Turnstile) | Se detiene después de 1 solicitud | `captcha` | Pedir una vía autorizada (API, exportación) | Sesión simulada + T09 |
| 429 / 503 | Se detiene sin reintentar | `rate_limit` / `overload` | Reducir la frecuencia y consultar los límites | Sesión simulada + T10 |
| 401 o formulario de contraseña inesperado | Se detiene | `auth_required` | Solo continuar con `auth.type=form` (Requests o navegador) o, en una API documentada, `auth.type=header` con un token emitido por el propietario | Sesión simulada + T08, T19, T20 |
| Página en ISO-8859-1 sin `charset` en la cabecera | Lee `<meta charset>`; si no lo hay, prueba UTF-8 y luego windows-1252 | — | — | Sesión simulada + fixture local (T17) |
| Contenido generado con JavaScript | Sugiere Navegador; el render compara el texto visible | — | Activar «Comparar con render» | Fixtures T03–T05 |
| API detectada pero no documentada | La marca «no verificado / no ejecutar» | Bloqueo en `run` | Conseguir la documentación pública del propietario | T16 |
| Estructura sin repeticiones claras | Sugiere un único campo `texto` | — | Escribir selectores a mano y probarlos con un archivo local | — (proceso manual) |

## Sitio «no visto» de prueba

`/nuevo/agenda` en el servidor de fixtures **no tiene YAML de ejemplo**. Tiene una estructura
distinta (`div.evento` con `h3` sin clase), está codificado en ISO-8859-1 declarado solo en
`<meta>` y pagina con `?pagina=N` mediante un enlace «Siguiente »». Recorrido verificado, solo con
la plantilla y las reglas sugeridas, sin editar nada a mano:

- Diagnóstico: `static_html`, confianza alta (0,75), 2 solicitudes.
- Sugerencia: registro `div.evento`; campos `titulo` (h3), `fecha`, `lugar`, `cupo` y `url`;
  paginación `url_template` con `pagina={page}`.
- Extracción: 7 eventos válidos con acentos correctos («Biblioteca Ñuñoa»). Se detiene por
  `max_pages=2`, el límite conservador de la plantilla (`completado_con_limites`).

Este recorrido sacó a la luz tres heurísticas débiles, ya corregidas:

- Los encabezados sin clase no se sugerían como campo.
- La paginación detectada no se proponía.
- Un enlace con el texto «datos abiertos» dentro de un registro se tomaba como documentación de API.

## Qué se ejecutó y qué no

- **Ejecutado (en esta máquina):**
  - `tests/integration/test_sitio_no_incluido.py`: 14 pruebas. Usan el sitio local no visto y
    una sesión HTTP simulada con dominios reservados `example.org`, sin red.
  - `tests/integration/test_gui.py`: 7 pruebas.
  - Casos T17 y T18 de la matriz.
- **No ejecutado:** ninguna prueba contra sitios públicos reales. Falta un sitio con autorización
  documentada. Las respuestas «reales» de la tabla son simulaciones de patrones conocidos y no
  garantizan cómo se comportará un sitio concreto.
- **Limitaciones conocidas:**
  - La detección de barreras y de estructura es heurística: puede haber protecciones sin marcadores
    visibles y estructuras que no se repiten de forma reconocible.
  - Una plantilla `url_template` sugerida empieza en la página 1 (`?pagina=1`). Si el sitio no
    acepta ese parámetro en la primera página, la vista previa lo mostrará y habrá que ajustarla.
