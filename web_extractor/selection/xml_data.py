"""XML -> estructura anidada equivalente a JSON, para reutilizar rutas con puntos.

Reglas de conversión (sin prefijos de espacio de nombres):
- elemento sin hijos ni atributos -> su texto;
- en otro caso, un dict con atributos como ``@nombre``, hijos por nombre local (repetidos -> lista)
  y el texto propio en ``text``.

Ejemplo: ``<data><item id="1"><pais id="MX">México</pais></item>...</data>`` permite
``records_path: item`` y campos ``pais.text`` / ``pais.@id``. El tamaño ya viene acotado por
``limits.max_response_bytes`` y el analizador expat de Python rechaza la expansión masiva de entidades.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _convert(element: ET.Element) -> Any:
    text = (element.text or "").strip()
    children = list(element)
    if not children and not element.attrib:
        return text or None
    node: dict[str, Any] = {f"@{_local(k)}": v for k, v in element.attrib.items()}
    for child in children:
        key, value = _local(child.tag), _convert(child)
        if key in node:
            if not isinstance(node[key], list):
                node[key] = [node[key]]
            node[key].append(value)
        else:
            node[key] = value
    if text:
        node["text"] = text
    return node


def xml_to_data(text: str) -> Any:
    """Convierte el elemento raíz; lanza ``ET.ParseError`` si el XML no es válido."""
    return _convert(ET.fromstring(text.lstrip("\ufeff \r\n\t")))
