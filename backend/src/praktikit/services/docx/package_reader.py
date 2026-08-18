"""Secure OOXML package reader (spec Section 11).

Wraps a validated ``.docx`` zip and provides read access to its parts with a
**hardened XML parser** (no network, no external entities, no DTD, no huge-tree).
Relationships are resolved from the package's ``.rels`` parts only — we never
fetch external resources.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from lxml import etree

from praktikit.core.exceptions import DocxValidationError, ParseError
from praktikit.services.docx.validator import (
    CONTENT_TYPES_PART,
    DOCUMENT_PART,
    validate_docx_file,
)

# Hardened parser: disable everything that could touch the network or blow up memory.
_xml_parser = etree.XMLParser(
    resolve_entities=False,  # no external/general entity expansion (XXE)
    no_network=True,  # never fetch external DTDs/entities
    load_dtd=False,  # don't load any DTD
    dtd_validation=False,
    huge_tree=False,  # cap document size to mitigate billion-looks style attacks
    recover=False,
)


def parse_xml_bytes(data: bytes) -> etree._Element:
    """Parse ``data`` with the hardened parser; raise :class:`ParseError` on failure."""
    try:
        return etree.fromstring(data, _xml_parser)
    except etree.XMLSyntaxError as exc:
        raise ParseError(f"XML tidak dapat di-parse: {exc}") from exc


@dataclass(frozen=True)
class Relationship:
    """One relationship entry from a ``.rels`` part."""

    rid: str
    rel_type: str  # namespace URI of the relationship type
    target: str  # part path (relative to the rels owner) for internal rels
    target_mode: str = "Internal"  # "Internal" | "External"
    external: bool = False


class DocxPackage:
    """Read-only, secure view over a validated DOCX package."""

    def __init__(self, path: Path, zf: ZipFile):
        self.path = path
        self._zf = zf
        self._names = set(zf.namelist())

    # -- construction ---------------------------------------------------------

    @classmethod
    def open(cls, path: str | os.PathLike) -> DocxPackage:
        """Validate then open ``path`` as a :class:`DocxPackage`."""
        p = validate_docx_file(path)
        try:
            zf = ZipFile(p, "r")
        except BadZipFile as exc:  # pragma: no cover - validate_docx_file guards this
            raise DocxValidationError(f"File ZIP rusak: {exc}") from exc
        return cls(p, zf)

    @classmethod
    @contextmanager
    def open_cm(cls, path: str | os.PathLike) -> Iterator[DocxPackage]:
        """Context-manager variant that closes the underlying zip on exit."""
        pkg = cls.open(path)
        try:
            yield pkg
        finally:
            pkg.close()

    def close(self) -> None:
        self._zf.close()

    # -- part access ----------------------------------------------------------

    def names(self) -> list[str]:
        return sorted(self._names)

    def has(self, part: str) -> bool:
        return part in self._names

    def read(self, part: str) -> bytes:
        if part not in self._names:
            raise KeyError(part)
        return self._zf.read(part)

    def read_xml(self, part: str) -> etree._Element:
        return parse_xml_bytes(self.read(part))

    def parts_with_prefix(self, prefix: str) -> list[str]:
        return [n for n in self._names if n.startswith(prefix)]

    # -- high-level helpers ---------------------------------------------------

    def document_element(self) -> etree._Element:
        """The root ``<w:document>`` element of ``word/document.xml``."""
        return self.read_xml(DOCUMENT_PART)

    def content_types_element(self) -> etree._Element:
        return self.read_xml(CONTENT_TYPES_PART)

    def relationships(self, part: str) -> dict[str, Relationship]:
        """Resolve relationships for a part, e.g. ``word/document.xml``.

        Looks up ``word/_rels/document.xml.rels``. External relationships are
        recorded but **never** fetched.
        """
        rels_part = _rels_part_for(part)
        if rels_part not in self._names:
            return {}
        root = self.read_xml(rels_part)
        out: dict[str, Relationship] = {}
        for rel in root:
            if etree.QName(rel.tag).localname != "Relationship":
                continue
            rid = rel.get("Id")
            if not rid:
                continue
            mode = rel.get("TargetMode", "Internal")
            out[rid] = Relationship(
                rid=rid,
                rel_type=rel.get("Type", ""),
                target=rel.get("Target", ""),
                target_mode=mode,
                external=(mode == "External"),
            )
        return out

    def resolve_target(self, owner_part: str, rel: Relationship) -> str | None:
        """Resolve an internal relationship target to a package part path.

        External relationships return ``None`` (never fetched).
        """
        if rel.external:
            return None
        return _resolve_relative(owner_part, rel.target)


def _rels_part_for(part: str) -> str:
    """Return the ``.rels`` part path that owns ``part`` (e.g. word/document.xml → word/_rels/document.xml.rels)."""
    slash = part.rfind("/")
    directory = part[:slash] if slash != -1 else ""
    filename = part[slash + 1 :]
    rels_dir = f"{directory}/_rels" if directory else "_rels"
    return f"{rels_dir}/{filename}.rels"


def _resolve_relative(owner: str, target: str) -> str:
    """Resolve ``target`` relative to the directory of ``owner`` (OOXML semantics)."""
    if target.startswith("/"):
        return target.lstrip("/")
    slash = owner.rfind("/")
    base = owner[:slash] if slash != -1 else ""
    segments = (base.split("/") if base else []) + target.split("/")
    resolved: list[str] = []
    for seg in segments:
        if seg == "" or seg == ".":
            continue
        if seg == "..":
            if resolved:
                resolved.pop()
            continue
        resolved.append(seg)
    return "/".join(resolved)
