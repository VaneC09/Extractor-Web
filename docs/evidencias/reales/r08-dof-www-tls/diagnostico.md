# Diagnóstico de `https://www.dof.gob.mx/`

- Fecha (UTC): 2026-11-21T21:07:13Z
- URL final: —
- Estado HTTP: —
- Tipo de contenido: —
- Solicitudes usadas: 1
- Diagnóstico detenido: sí

## Incidencias

- **tls_error** — Certificado TLS inválido; no se desactiva la verificación — evidencia: Hostname mismatch, certificate is not valid for 'www.dof.gob.mx (https://www.dof.gob.mx/robots.txt). Siguiente paso legítimo: Detener: el certificado TLS no es válido para este dominio. No se desactiva la verificación; usar la dirección oficial con certificado válido (p. ej. la variante con o sin 'www', si el propietario la publica) o avisar al propietario.

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
