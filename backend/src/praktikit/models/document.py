"""Document-level metadata: page layout, margins, sections, styles.

Units: OOXML stores page geometry and indents/spacing in **twips** (1/1440 inch,
1/20 of a point). We keep raw twips here so values can be round-tripped exactly,
and provide display helpers (``to_cm``) for the UI/debug output.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

TWIPS_PER_CM = 567.0  # 1 cm = 567 twips (1440 twips/inch, 2.54 cm/inch)


class Orientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class PageLayout(BaseModel):
    """Physical page size + orientation for a section."""

    model_config = ConfigDict(extra="ignore")

    width_twips: int | None = None
    height_twips: int | None = None
    orientation: Orientation = Orientation.PORTRAIT
    # Best-effort size name derived from dimensions ("A4", "Letter", …) or None.
    size_name: str | None = None


class Margins(BaseModel):
    """Page margins in twips. Fields are ``None`` when not specified in the source."""

    model_config = ConfigDict(extra="ignore")

    top: int | None = None
    bottom: int | None = None
    left: int | None = None
    right: int | None = None
    gutter: int | None = None
    header: int | None = None  # distance from top to header
    footer: int | None = None  # distance from bottom to footer

    def to_cm(self) -> dict[str, float | None]:
        """Return margins in centimetres for display."""

        def cm(v: int | None) -> float | None:
            return None if v is None else round(v / TWIPS_PER_CM, 2)

        return {
            "top": cm(self.top),
            "bottom": cm(self.bottom),
            "left": cm(self.left),
            "right": cm(self.right),
            "gutter": cm(self.gutter),
        }


class SectionMeta(BaseModel):
    """A document section (``<w:sectPr>``)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    index: int
    page_layout: PageLayout = PageLayout()
    margins: Margins = Margins()
    # Header/footer presence flags.
    has_header: bool = False
    has_footer: bool = False
    has_first_page_header_footer: bool = False
    different_first_page: bool = False
    even_and_odd_headers: bool = False
    title_pg: bool = False
    # Relationship ids (kept so we can preserve/inspect them; never logged).
    header_rids: list[str] = []
    footer_rids: list[str] = []


class StyleInfo(BaseModel):
    """A summary of one style from ``styles.xml``."""

    model_config = ConfigDict(extra="ignore")

    style_id: str
    name: str
    style_type: str = "paragraph"  # paragraph | character | table | numbering
    based_on: str | None = None
    is_heading: bool = False
    heading_level: int | None = None
    font_name: str | None = None
    font_size: float | None = None  # points


class DocumentMeta(BaseModel):
    """Top-level document properties (primary section used for summary)."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    core_creator: str | None = None
    page_layout: PageLayout = PageLayout()
    margins: Margins = Margins()
    section_count: int = 1
    sections: list[SectionMeta] = []
    styles: list[StyleInfo] = []
    numbering_definition_count: int = 0
    has_headers: bool = False
    has_footers: bool = False
    has_table_of_contents: bool = False
    toc_is_field: bool | None = None  # True=Word TOC field, False=manual text
