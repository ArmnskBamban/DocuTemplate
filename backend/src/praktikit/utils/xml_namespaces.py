"""OOXML / OpenXML namespace helpers.

We manipulate raw WordprocessingML via lxml (spec Section 23 / Section 41), so a
central namespace map and a ``qn()`` qualified-name helper keep the rest of the
codebase readable and consistent with python-docx conventions.
"""

from __future__ import annotations

from lxml import etree

# Namespace prefix -> URI map for the parts of OOXML we touch.
NSMAP: dict[str, str] = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
}

# Reverse lookup: URI -> preferred prefix (for serialization).
NSMAP_REVERSE: dict[str, str] = {uri: prefix for prefix, uri in NSMAP.items()}


def qn(tag: str) -> str:
    """Return Clark-notation for a tag like ``w:p`` or a path like ``w:pPr/w:outlineLvl``.

    Each slash-separated segment is independently qualified, so
    ``"w:pPr/w:outlineLvl"`` → ``"{w-uri}pPr/{w-uri}outlineLvl"``.
    This works with ``lxml.etree.find()`` which accepts Clark notation paths.
    """
    segments = tag.split("/")
    parts: list[str] = []
    for seg in segments:
        if ":" not in seg:
            # Default to the WordprocessingML namespace when no prefix given.
            parts.append(f"{{{NSMAP['w']}}}{seg}")
        else:
            prefix, local = seg.split(":", 1)
            try:
                uri = NSMAP[prefix]
            except KeyError as exc:  # pragma: no cover - defensive
                raise ValueError(f"Unknown namespace prefix: {prefix!r}") from exc
            parts.append(f"{{{uri}}}{local}")
    return "/".join(parts)


def localname(element: etree._Element) -> str:
    """Return the local name of an element (without namespace prefix/URI)."""
    tag = etree.QName(element.tag).localname
    return tag


def prefixed(element: etree._Element) -> str:
    """Return ``prefix:local`` for an element using our namespace map."""
    qn_obj = etree.QName(element.tag)
    prefix = NSMAP_REVERSE.get(qn_obj.namespace, qn_obj.namespace or "")
    return f"{prefix}:{qn_obj.localname}" if prefix else qn_obj.localname


def find(element: etree._Element, tag: str):
    """``element.find`` using a ``qn()``-qualified ``tag`` (first match or None)."""
    return element.find(qn(tag))


def findall(element: etree._Element, tag: str) -> list[etree._Element]:
    """``element.findall`` using a ``qn()``-qualified ``tag``."""
    return element.findall(qn(tag))


def findtext(element: etree._Element, tag: str, default: str = "") -> str:
    """``element.findtext`` using a ``qn()``-qualified ``tag``."""
    return element.findtext(qn(tag), default=default)
