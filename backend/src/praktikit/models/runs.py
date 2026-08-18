"""Run-level formatting (``<w:r>`` properties).

Mirrors python-docx's tri-state semantics: ``None`` means "inherit / not set"
so we can faithfully round-trip the source document instead of collapsing
unknowns to ``False``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RunFormat(BaseModel):
    """Character formatting extracted from a run's ``<w:rPr>``."""

    model_config = ConfigDict(extra="ignore")

    font_name: str | None = None
    # Font size in **points** (OOXML stores half-points; we convert on read).
    font_size: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    color: str | None = None  # hex RGB, e.g. "FF0000"
    highlight: str | None = None
    all_caps: bool | None = None
    small_caps: bool | None = None
    # "superscript" | "subscript" | None (from <w:vertAlign w:val=...>)
    vert_align: str | None = None

    def to_fingerprint(self) -> tuple:
        """A hashable, comparison-friendly summary used by the style analyzer."""
        return (
            round(self.font_size, 1) if self.font_size is not None else None,
            bool(self.bold),
            bool(self.italic),
            bool(self.all_caps),
            bool(self.small_caps),
            self.font_name,
        )


class RunData(BaseModel):
    """A run's text together with its formatting."""

    model_config = ConfigDict(extra="ignore")

    text: str = ""
    format: RunFormat = RunFormat()

    @property
    def is_bold(self) -> bool:
        return bool(self.format.bold)
