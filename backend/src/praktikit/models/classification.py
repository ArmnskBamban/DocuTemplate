"""Semantic element classification (spec Section 15).

Every block is assigned a :class:`SemanticRole` plus a confidence score and the
human-readable reasons/signals that produced it. Confidence drives automation
(spec Section 48): high → auto, medium → auto+flag, low → require review.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class SemanticRole(StrEnum):
    COVER_STATIC = "cover_static"  # UNIVERSITAS, FAKULTAS, LAPORAN PRAKTIKUM, …
    COVER_VARIABLE = "cover_variable"  # identity fields on the cover
    TITLE = "title"
    CHAPTER_HEADING = "chapter_heading"  # BAB I / I. / 1 / CHAPTER I
    SECTION_HEADING = "section_heading"  # 1.1 / A.
    SUBSECTION_HEADING = "subsection_heading"  # 1.1.1 / A.1
    BODY_CONTENT = "body_content"  # the report's prose — must be cleared
    INSTRUCTION_TEXT = "instruction_text"  # leftover instructions
    TABLE_TEMPLATE = "table_template"  # header + repeated result rows
    TABLE_CONTENT = "table_content"  # pure old-result table
    TABLE_IDENTITY = "table_identity"  # Nama|John style cover table
    CAPTION = "caption"  # "Gambar 1", "Tabel 1"
    IMAGE_LOGO = "image_logo"
    IMAGE_CONTENT = "image_content"
    REFERENCES_HEADING = "references_heading"
    REFERENCES_CONTENT = "references_content"
    APPENDIX_HEADING = "appendix_heading"
    APPENDIX_CONTENT = "appendix_content"
    PAGE_BREAK = "page_break"
    BLANK = "blank"
    UNKNOWN = "unknown"


class Automation(StrEnum):
    """How a classified element should be handled by default."""

    AUTO = "auto"  # confidence high → act automatically
    REVIEW = "review"  # confidence medium → act but flag for review
    KEEP = "keep"  # confidence low → never destructive, default keep


class Classification(BaseModel):
    """The result of classifying a single block."""

    model_config = ConfigDict(extra="ignore")

    block_id: str
    role: SemanticRole
    confidence: float = 0.0
    reasons: list[str] = []
    signals: dict[str, float] = {}  # signal name -> contribution (explainability)
    automation: Automation = Automation.KEEP


def automation_for_confidence(confidence: float, auto_threshold: float, review_threshold: float) -> Automation:
    """Map a confidence value to an :class:`Automation` bucket."""
    if confidence >= auto_threshold:
        return Automation.AUTO
    if confidence >= review_threshold:
        return Automation.REVIEW
    return Automation.KEEP
