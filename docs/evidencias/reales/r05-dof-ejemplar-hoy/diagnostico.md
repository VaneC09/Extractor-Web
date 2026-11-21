# Diagnóstico de `https://dof.gob.mx/index.php`

- Fecha (UTC): 2026-11-21T20:40:46Z
- URL final: https://dof.gob.mx/index.php
- Estado HTTP: 200
- Tipo de contenido: text/html; charset=utf-8
- Solicitudes usadas: 2
- Diagnóstico detenido: no

## Métodos sugeridos

| Método | Puntuación | Confianza | Ejecutable | Requisitos |
|---|---|---|---|---|
| static_html | 0.85 | alta | sí | — |
| structured_file | 0.50 | media | sí | Confirmar que el archivo es público, autorizado y su licencia permite el uso |
| browser | 0.35 | baja | sí | Requiere Selenium con Chrome o Edge; mayor coste por página: usar topes bajos |
| api | 0.00 | baja | no verificado / no ejecutar | No verificado / no ejecutar: falta confirmar una API pública y documentada (extraction.api.documented + documentation_url) |

### static_html
- A favor: Hay texto sustancial en el HTML inicial (+0.20)
- A favor: Estructura repetida candidata a registro: 'li.TabbedPanelsTab' ×5 (+0.15)
- A favor: Indicios de paginación por enlaces (+0.10)
- A favor: Control 'cargar más' (a con enlace) (+0.10)

### structured_file
- A favor: 1 enlace(s) a archivos estructurados descargables (+0.50)

### browser
- A favor: Aviso <noscript> que pide habilitar JavaScript (+0.15)
- A favor: 6 elemento(s) que muestran contenido al interactuar (pestañas, desplegables, clics): ese contenido puede no estar en el HTML inicial (+0.10)

## Hallazgos (indicios heurísticos)

| Código | Categoría | Descripción | Evidencia |
|---|---|---|---|
| response.status | respuesta | HTTP 200, text/html; charset=utf-8, 90,037 caracteres | vía http |
| html.summary | dom | Título: 'DOF - Diario Oficial de la Federación'; 745 elementos; 8,363 caracteres de texto visible; 30 scripts | DOF - Diario Oficial de la Federación Usuario Clave Entrar ¿Olvidó su usuario? Inicio \| Contacto \| Mapa del Sitio \| Ayuda . Busqueda Ejemplar de hoy Trámites |
| js.noscript | renderizado | Aviso <noscript> que pide habilitar JavaScript | Su navagedor no soporta JavaScript! |
| html.text_present | dom | Hay texto sustancial en el HTML inicial | 8363 caracteres |
| html.tables | tabla | 23 tabla(s) HTML; 0 con encabezados | [{"selector": "table:nth-of-type(1)", "headers": [], "rows": 89}, {"selector": "table:nth-of-type(2)", "headers": [], "rows": 5}, {"selector": "table:nth-of-typ |
| html.repeated | estructura | Estructura repetida candidata a registro: 'li.TabbedPanelsTab' ×5 | span.resaltado, span.desc_sec |
| html.pagination | paginación | Indicios de paginación por enlaces | parámetro de página -> nota_to_imagen_fs.php?cod_diario=330965&pagina=0&fecha=20/11/2026 |
| html.load_more | bajo demanda | Control 'cargar más' (a con enlace) | <a class="enlaces" href="indicadores.php" style="float: right;">Ver más</a> |
| html.data_files | estructurado | 1 enlace(s) a archivos estructurados descargables | https://dof.gob.mx/sumario.xml |
| html.login_form | acceso | Formulario con contraseña: el contenido puede requerir autenticación. Solo continuar con autorización expresa y credenciales propias |  |
| dom.interaction | interacción | 6 elemento(s) que muestran contenido al interactuar (pestañas, desplegables, clics): ese contenido puede no estar en el HTML inicial | input, a.ayuda_contextual, img, a |
| time.dependent | tiempo | El contenido depende del momento de la consulta (actualización, caducidad o fecha). Cada registro guarda su fecha de adquisición; repetir la extracción puede dar otros datos | 57 enlaces parametrizados por fecha, p. ej. /nota_detalle.php?codigo=5804497&fecha=20/11/1926; expires: Thu, 19 Nov 1981 08:52:00 GMT |

## Limitaciones del diagnóstico

- Se analiza una sola respuesta del documento objetivo (más robots.txt); el contenido puede variar por usuario, región, hora o pruebas A/B.
- Sin render opcional no se ejecuta JavaScript: los indicios de renderizado en cliente son heurísticos.
- No se exploran rutas no enlazadas ni se infieren o prueban endpoints/APIs no documentados.
- La detección de CAPTCHA, bloqueos o protecciones es heurística: puede haber falsos positivos y negativos.
- La herramienta no puede verificar la autorización legal ni los términos de uso; dependen de la confirmación humana registrada en la configuración.
- https://dof.gob.mx/robots.txt leído

## Candidatos detectados

```json
{
  "tables": [
    {
      "selector": "table:nth-of-type(1)",
      "headers": [],
      "rows": 89
    },
    {
      "selector": "table:nth-of-type(2)",
      "headers": [],
      "rows": 5
    },
    {
      "selector": "table:nth-of-type(3)",
      "headers": [],
      "rows": 9
    },
    {
      "selector": "table:nth-of-type(4)",
      "headers": [],
      "rows": 9
    },
    {
      "selector": "table:nth-of-type(5)",
      "headers": [],
      "rows": 21
    },
    {
      "selector": "table:nth-of-type(6)",
      "headers": [],
      "rows": 21
    },
    {
      "selector": "table:nth-of-type(7)",
      "headers": [],
      "rows": 18
    },
    {
      "selector": "table:nth-of-type(8)",
      "headers": [],
      "rows": 13
    },
    {
      "selector": "table:nth-of-type(9)",
      "headers": [],
      "rows": 1
    },
    {
      "selector": "table:nth-of-type(10)",
      "headers": [],
      "rows": 1
    },
    {
      "selector": "table:nth-of-type(11)",
      "headers": [],
      "rows": 2
    },
    {
      "selector": "table:nth-of-type(12)",
      "headers": [],
      "rows": 2
    },
    {
      "selector": "table:nth-of-type(13)",
      "headers": [],
      "rows": 1
    },
    {
      "selector": "table#table_menu_right",
      "headers": [],
      "rows": 21
    },
    {
      "selector": "table:nth-of-type(15)",
      "headers": [],
      "rows": 7
    },
    {
      "selector": "table:nth-of-type(16)",
      "headers": [],
      "rows": 5
    },
    {
      "selector": "table:nth-of-type(17)",
      "headers": [],
      "rows": 1
    },
    {
      "selector": "table:nth-of-type(18)",
      "headers": [],
      "rows": 1
    },
    {
      "selector": "table:nth-of-type(19)",
      "headers": [],
      "rows": 13
    },
    {
      "selector": "table:nth-of-type(20)",
      "headers": [],
      "rows": 2
    },
    {
      "selector": "table:nth-of-type(21)",
      "headers": [],
      "rows": 6
    },
    {
      "selector": "table:nth-of-type(22)",
      "headers": [],
      "rows": 4
    },
    {
      "selector": "table:nth-of-type(23)",
      "headers": [],
      "rows": 2
    }
  ],
  "record_selectors": [
    {
      "selector": "li.TabbedPanelsTab",
      "count": 5,
      "avg_text": 61,
      "child_selectors": [
        "span.resaltado",
        "span.desc_sec"
      ],
      "has_link": true
    },
    {
      "selector": "div.tab_content2",
      "count": 3,
      "avg_text": 1129,
      "child_selectors": [
        "a.enlaces_leido"
      ],
      "has_link": true
    }
  ],
  "data_files": [
    {
      "url": "https://dof.gob.mx/sumario.xml",
      "text": "",
      "same_host": true
    }
  ]
}
```
