# Diagnóstico de `https://data.worldbank.org/`

- Fecha (UTC): 2026-11-21T20:42:36Z
- URL final: —
- Estado HTTP: 403
- Tipo de contenido: —
- Solicitudes usadas: 2
- Diagnóstico detenido: sí

## Incidencias

- **bot_challenge** — HTTP 403 con desafío anti-bot — evidencia: <!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title><meta http-equiv="Content-Type" content= (https://data.worldbank.org/). Siguiente paso legítimo: Detener: desafío anti-bot detectado. No evadir; usar una API o descarga oficial documentada por el propietario, o solicitar acceso autorizado.

## Métodos sugeridos

| Método | Puntuación | Confianza | Ejecutable | Requisitos |
|---|---|---|---|---|

## Hallazgos (indicios heurísticos)

| Código | Categoría | Descripción | Evidencia |
|---|---|---|---|

## Limitaciones del diagnóstico

- Se analiza una sola respuesta del documento objetivo (más robots.txt); el contenido puede variar por usuario, región, hora o pruebas A/B.
- Sin render opcional no se ejecuta JavaScript: los indicios de renderizado en cliente son heurísticos.
- No se exploran rutas no enlazadas ni se infieren o prueban endpoints/APIs no documentados.
- La detección de CAPTCHA, bloqueos o protecciones es heurística: puede haber falsos positivos y negativos.
- La herramienta no puede verificar la autorización legal ni los términos de uso; dependen de la confirmación humana registrada en la configuración.
- https://data.worldbank.org/robots.txt devolvió 403: sin restricciones publicadas
