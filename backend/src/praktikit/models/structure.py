"""Detected document structure: headings, hierarchy, cover region (spec Section 14/31)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HeadingInfo(BaseModel):
    """A detected heading with its level, parsed number and evidence."""

    model_config = ConfigDict(extra="ignore")

    block_id: str
    level: int  # 0 = chapter/major, 1 = section, 2 = subsection, …
    title: str
    number: str | None = None  # "I", "1.1", "A.", "III" …
    number_scheme: str | None = None  # "bab" | "chapter" | "decimal" | "roman" | "letter" | "manual"
    confidence: float = 0.0
    reasons: list[str] = []


class StructureNode(BaseModel):
    """A node in the detected document tree (cover → chapters → sections …)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    node_type: str  # "cover" | "chapter" | "section" | "subsection" | "body" | "references" | "appendix"
    title: str | None = None
    number: str | None = None
    level: int = 0
    block_id: str | None = None  # heading block this node represents (None for cover root)
    children: list[StructureNode] = []

    def walk(self):
        """Yield this node and all descendants in pre-order."""
        yield self
        for child in self.children:
            yield from child.walk()


StructureNode.model_rebuild()
