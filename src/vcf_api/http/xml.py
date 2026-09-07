from collections.abc import Mapping, Sequence
from xml.etree.ElementTree import Element, SubElement, tostring


def to_xml(payload: Mapping[str, object], root_name: str = "response") -> bytes:
    root = Element(root_name)
    _append_mapping(root, payload)
    return tostring(root, encoding="utf-8", xml_declaration=True)


def _append_mapping(parent: Element, payload: Mapping[str, object]) -> None:
    for key, value in payload.items():
        child = SubElement(parent, str(key))
        _append_value(child, value)


def _append_value(element: Element, value: object) -> None:
    if value is None:
        element.set("nil", "true")
    elif isinstance(value, Mapping):
        _append_mapping(element, value)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            child = SubElement(element, "item")
            _append_value(child, item)
    elif isinstance(value, bool):
        element.text = str(value).lower()
    else:
        element.text = str(value)
