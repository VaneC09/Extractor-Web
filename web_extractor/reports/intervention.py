"""Intervención humana: qué debe hacer una persona cuando un flujo se detiene y dónde queda registrado.

Cada incidencia que requiere a una persona se guarda en la carpeta del diagnóstico, vista previa o
ejecución (``intervencion_humana.md`` y ``.json``) y se añade al registro central
``<output>/intervenciones.jsonl``. La herramienta nunca supera la barrera por sí misma: solo indica
la vía legítima.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from web_extractor.models.results import Incident
from web_extractor.utils.timeutils import utc_now_iso

INTERVENTION_LOG = "intervenciones.jsonl"
GENERAL_LOG = "web_extractor.log"

ANSWERS = {
    "si_con_credenciales": "Sí, si el propietario le dio un usuario y contraseña o un token autorizado.",
    "tras_ajuste": "Sí, después de corregir lo indicado.",
    "con_persona_captcha": "Sí, solo con la estrategia Navegador y si usted mismo lo resuelve en la ventana "
    "visible; la herramienta no lo resuelve.",
    "con_persona": "Sí, si usted, titular de la cuenta, escribe el código que recibe cuando la herramienta lo pida.",
    "mas_tarde": "Más tarde, con una frecuencia menor y solo si el propietario lo admite.",
    "no": "No de forma automática: hace falta una vía autorizada por el propietario.",
}

CREDENTIAL_STEPS = [
    "Confirme con el propietario del sitio que la cuenta o el token le autoriza a extraer estos datos con esta "
    "finalidad. Guarde esa evidencia (correo, contrato) y anótela en «Permiso o licencia de uso».",
    "Guarde las credenciales en variables de entorno de la terminal desde la que abre la herramienta, nunca en la "
    "configuración, en capturas ni en archivos de ejemplo. PowerShell: `$env:WE_USUARIO=\"…\"` y "
    "`$env:WE_CLAVE=\"…\"`, o `$env:WE_TOKEN=\"…\"`; después `python -m web_extractor gui`.",
    "Interfaz: sección «Configuración y ejecución de la extracción» → «Acceso autorizado». Elija «Usuario y "
    "contraseña» (página de inicio de sesión y nombres de las variables) o «Token o API key documentado» "
    "(encabezado y nombre de la variable). CLI: sección `auth` del YAML (`type: form` o `type: header`).",
    "Pulse «Vista previa»: inicia sesión una sola vez. Si las credenciales se rechazan, se detiene sin reintentar "
    "(incidencia `auth_failed`).",
    "Si la vista previa muestra los registros, pulse «Iniciar extracción».",
]

GUIDES: dict[str, dict] = {
    "auth_required": {
        "title": "El sitio pide iniciar sesión o un token",
        "can_continue": "si_con_credenciales",
        "steps": CREDENTIAL_STEPS,
    },
    "auth_failed": {
        "title": "Las credenciales autorizadas fueron rechazadas",
        "can_continue": "tras_ajuste",
        "steps": [
            "No vuelva a intentarlo en bucle: el sitio puede bloquear la cuenta.",
            "Verifique con el propietario que el usuario, la contraseña o el token siguen vigentes y autorizados.",
            "Revise que las variables de entorno estén definidas en la misma terminal que abrió la herramienta "
            "(la interfaz muestra ✓/✗ junto a cada nombre).",
            "Repita una sola «Vista previa» después de corregirlo.",
        ],
    },
    "mfa_required": {
        "title": "El sitio pide un código de verificación (autenticación en dos pasos)",
        "can_continue": "con_persona",
        "steps": [
            "La herramienta no lee SMS ni correos, no genera códigos ni usa servicios externos: el código lo "
            "escribe usted, titular de la cuenta autorizada.",
            "Interfaz: en «Acceso autorizado» active «Pedirme el código de verificación». CLI: "
            "`auth.ask_verification_code: true` en el YAML.",
            "Pulse «Iniciar extracción» (la vista previa no pide el código). Cuando aparezca el cuadro "
            "«Código de verificación», escriba el código recibido y pulse «Enviar código»; tiene 5 minutos.",
            "El código se oculta en los logs y no se guarda. Si se rechaza, se detiene sin reintentar "
            "(incidencia `auth_failed`); pida un código nuevo y repita una sola vez.",
            "Si el inicio de sesión muestra un CAPTCHA, solo continúa con la estrategia Navegador y «Resolveré yo "
            "el CAPTCHA»: lo resuelve usted en la ventana; por HTTP se detiene.",
        ],
    },
    "access_denied": {
        "title": "Acceso denegado (HTTP 403)",
        "can_continue": "no",
        "steps": [
            "Confirme con el propietario si el recurso está autorizado para esta finalidad.",
            "Si el propietario le entrega una cuenta o un token para este uso, siga los pasos de acceso autorizado: "
            + " ".join(CREDENTIAL_STEPS[1:3]),
            "Si no hay autorización, no continúe con este recurso.",
        ],
    },
    "paywall": {
        "title": "Contenido de pago o suscripción",
        "can_continue": "no",
        "steps": [
            "No eluda el muro de pago.",
            "Obtenga una licencia o suscripción que permita expresamente el uso automatizado.",
            "Si esa licencia incluye una cuenta o token para este uso, configúrelo como acceso autorizado: "
            + " ".join(CREDENTIAL_STEPS[1:3]),
        ],
    },
    "captcha": {
        "title": "CAPTCHA",
        "can_continue": "con_persona_captcha",
        "steps": [
            "La herramienta no resuelve ni evade ningún CAPTCHA (casilla, imágenes, rompecabezas o deslizador) "
            "y no lo envía a servicios de resolución.",
            "Para continuar, **usted mismo** debe resolverlo: elija la estrategia «Navegador» y active «Resolveré "
            "yo el CAPTCHA» (CLI: `extraction.browser.human_verification: true`). Se abre una ventana visible.",
            "Resuélvalo en esa ventana. La herramienta espera hasta 5 minutos sin hacer solicitudes y continúa "
            "sola cuando la verificación desaparece. Queda registrado en la bitácora (`human_verification`).",
            "Si el CAPTCHA se repite más de 3 veces, la herramienta se detiene: el sitio no admite ese ritmo de "
            "acceso. Aumente la pausa, reduzca páginas o pida una vía autorizada.",
            "Resolver el CAPTCHA no sustituye la autorización: si los términos del sitio prohíben el acceso "
            "automatizado, use el modo «Solo diagnosticar» o pida al propietario una API o descarga oficial.",
        ],
    },
    "bot_challenge": {
        "title": "Desafío anti-bot",
        "can_continue": "con_persona_captcha",
        "steps": [
            "No intente evadirlo (sin proxies, sin cambiar la huella del navegador, sin reintentos).",
            "Para continuar, **usted mismo** debe resolverlo: elija la estrategia «Navegador» y active «Resolveré "
            "yo el CAPTCHA» (CLI: `extraction.browser.human_verification: true`). Se abre una ventana visible.",
            "Resuélvalo en esa ventana. La herramienta espera hasta 5 minutos sin hacer solicitudes y continúa "
            "sola cuando la verificación desaparece. Queda registrado en la bitácora (`human_verification`).",
            "Si el CAPTCHA se repite más de 3 veces, la herramienta se detiene: el sitio no admite ese ritmo de "
            "acceso. Aumente la pausa, reduzca páginas o pida una vía autorizada.",
            "Resolver el CAPTCHA no sustituye la autorización: si los términos del sitio prohíben el acceso "
            "automatizado, use el modo «Solo diagnosticar» o pida al propietario una API o descarga oficial.",
        ],
    },
    "rate_limit": {
        "title": "Límite de solicitudes (HTTP 429)",
        "can_continue": "mas_tarde",
        "steps": [
            "Deténgase y espere al menos lo indicado en `Retry-After` (aparece en la evidencia).",
            "Consulte con el propietario los límites admitidos.",
            "Vuelva a intentarlo otro día con una pausa mayor y menos páginas.",
        ],
    },
    "overload": {
        "title": "Servidor sobrecargado o en mantenimiento (HTTP 503)",
        "can_continue": "mas_tarde",
        "steps": [
            "Deténgase: no agregue carga al servidor.",
            "Vuelva a intentarlo más tarde con una pausa mayor y menos páginas.",
        ],
    },
    "tls_error": {
        "title": "Certificado TLS inválido",
        "can_continue": "tras_ajuste",
        "steps": [
            "La herramienta no desactiva la verificación del certificado.",
            "Use la dirección oficial con certificado válido (por ejemplo la variante con o sin «www» que publique "
            "el propietario) y analice esa URL.",
            "Si no existe, avise al propietario.",
        ],
    },
    "robots_disallow": {
        "title": "robots.txt prohíbe la ruta",
        "can_continue": "no",
        "steps": [
            "La herramienta respeta robots.txt.",
            "Solicite al propietario una vía alternativa autorizada (API o descarga) y analice esa URL.",
        ],
    },
    "out_of_scope": {
        "title": "Recurso fuera del dominio o ruta permitidos",
        "can_continue": "tras_ajuste",
        "steps": [
            "Compruebe que el otro dominio pertenece al mismo propietario y está autorizado.",
            "Si lo está, analice directamente esa URL (el alcance se ajusta a la URL analizada) o añádalo en "
            "`scope.allowed_domains` del YAML. Si no, omita el recurso.",
        ],
    },
    "authorization": {
        "title": "Falta completar la autorización",
        "can_continue": "tras_ajuste",
        "steps": ["Complete la sección «Autorización» (quién autoriza, permiso o licencia, finalidad y confirmación)."],
    },
    "empty_page": {
        "title": "Página sin registros con las reglas actuales",
        "can_continue": "tras_ajuste",
        "steps": [
            "Puede ser un cambio de estructura del sitio.",
            "En «Datos a extraer» revise el selector de registros y los campos, y pulse «Vista previa».",
        ],
    },
    "change_detected": {
        "title": "La estructura del sitio cambió",
        "can_continue": "tras_ajuste",
        "steps": [
            "Compare los cambios listados en el informe con el sitio.",
            "Ajuste selectores o campos en «Datos a extraer» y valide con «Vista previa» antes de volver a extraer.",
        ],
    },
}


def guide_for(kind: str) -> dict | None:
    guide = GUIDES.get(kind)
    if guide is None:
        return None
    return {**guide, "answer": ANSWERS[guide["can_continue"]]}


def intervention_entries(incidents: Iterable[Incident], *, stage: str, project: str, target_url: str) -> list[dict]:
    entries = []
    for incident in incidents:
        guide = guide_for(incident.kind)
        if guide is None:
            continue
        entries.append({
            "timestamp": incident.timestamp, "stage": stage, "project": project, "target_url": target_url,
            "kind": incident.kind, "title": guide["title"], "message": incident.message, "url": incident.url,
            "can_continue": guide["can_continue"], "answer": guide["answer"], "steps": guide["steps"],
        })
    return entries


def intervention_markdown(entries: list[dict]) -> str:
    lines = ["# Intervención humana requerida", ""]
    for e in entries:
        lines += [
            f"## {e['title']} (`{e['kind']}`)", "",
            f"- Etapa: {e['stage']} · Fecha (UTC): {e['timestamp']}",
            f"- URL: {e['url'] or e['target_url']}",
            f"- Detalle: {e['message']}",
            f"- **¿Se puede continuar?** {e['answer']}", "",
            "Pasos:", "",
            *[f"{i}. {step}" for i, step in enumerate(e["steps"], 1)], "",
        ]
    lines.append("La herramienta no supera barreras por sí misma: solo continúa por la vía autorizada indicada.")
    return "\n".join(lines) + "\n"


def write_intervention(entries: list[dict], directory: Path, output_root: Path) -> dict[str, str]:
    """Guarda los pasos en la carpeta del evento y los añade al registro central."""
    if not entries:
        return {}
    directory.mkdir(parents=True, exist_ok=True)
    md, js = directory / "intervencion_humana.md", directory / "intervencion_humana.json"
    md.write_text(intervention_markdown(entries), encoding="utf-8")
    js.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    output_root.mkdir(parents=True, exist_ok=True)
    with (output_root / INTERVENTION_LOG).open("a", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps({**entry, "recorded_at": utc_now_iso(), "file": str(md)}, ensure_ascii=False) + "\n")
    return {"intervention": str(md), "intervention_json": str(js)}
