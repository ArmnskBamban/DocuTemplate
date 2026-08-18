"""Ordered document block model (spec Section 13).

The body of ``word/document.xml`` is walked once in element order. Each child
becomes a :class:`DocumentBlock` with a **stable positional id** (``p-000001``,
``tbl-000001``, ``img-000001``). Order is sacred: we never iterate
``document.paragraphs`` / ``document.tables`` separately.

Because mutation runs on a byte-identical clone of the source, re-walking
assigns the same ids — so a :class:`~praktikit.models.cleaning.CleaningPlan`
refers to elements by id and the mutation engine resolves them 1:1.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from praktikit.models.document import SectionMeta
from praktikit.models.runs import RunData, RunFormat


class BlockType(StrEnum):
    PARAGRAPH = "paragraph"
    TABLE = "table"
    SECTION_BOUNDARY = "section_boundary"


class Numbering(BaseModel):
    """Paragraph numbering reference (``<w:numPr>``)."""

    model_config = ConfigDict(extra="ignore")

    num_id: int | None = None
    ilvl: int | None = None
    is_list: bool = False  # True when a numbering definition is attached


class ParagraphProps(BaseModel):
    """Paragraph properties (``<w:pPr>``) captured for detection & preservation."""

    model_config = ConfigDict(extra="ignore")

    style_id: str | None = None
    style_name: str | None = None
    alignment: str | None = None  # left | center | right | justify | both
    outline_level: int | None = None  # <w:outlineLvl w:val=...> (0 = top)
    # Indentation in twips (None = not set).
    left_indent: int | None = None
    right_indent: int | None = None
    first_line_indent: int | None = None
    # Spacing in twips (None = not set).
    space_before: int | None = None
    space_after: int | None = None
    line_spacing: float | None = None  # lines (1.0, 1.5, …) or None
    keep_with_next: bool = False
    keep_together: bool = False
    page_break_before: bool = False
    numbering: Numbering | None = None
    contains_page_break: bool = False
    contains_image: bool = False
    contains_field: bool = False
    has_section_properties: bool = False  # mid-document section break lives in pPr


class ImageInfo(BaseModel):
    """An image (``<w:drawing>``) located inside a paragraph's run.

    ``id`` is a global positional id (``img-000001``); ``parent_paragraph_id``
    points back to the enclosing paragraph block.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    parent_paragraph_id: str
    rel_id: str | None = None  # r:embed / r:link relationship id
    target: str | None = None  # media part path (e.g. word/media/image1.png)
    inline: bool = True  # inline vs anchored
    width_emu: int | None = None
    height_emu: int | None = None


class ParagraphBlock(BaseModel):
    """A ``<w:p>`` block."""

    model_config = ConfigDict(extra="ignore")

    id: str
    index: int  # ordinal among ALL blocks
    block_type: BlockType = BlockType.PARAGRAPH
    text: str = ""
    runs: list[RunData] = []
    props: ParagraphProps = ParagraphProps()
    images: list[ImageInfo] = []  # images anchored in this paragraph
    # Assigned by detection layers:
    style_fingerprint: tuple | None = None

    @property
    def is_blank(self) -> bool:
        return not self.text.strip()

    @property
    def plain_format(self) -> RunFormat:
        """Representative run format (first run), used as a fallback anchor."""
        return self.runs[0].format if self.runs else RunFormat()


class CellInfo(BaseModel):
    """A table cell (``<w:tc>``)."""

    model_config = ConfigDict(extra="ignore")

    row_index: int
    col_index: int
    text: str = ""
    grid_span: int = 1  # horizontal merge (<w:gridSpan>)
    v_merge: str | None = None  # "restart" | "continue" | None
    style_id: str | None = None

    @property
    def is_blank(self) -> bool:
        return not self.text.strip()


class TableBlock(BaseModel):
    """A ``<w:tbl>`` block, modelled as a 2-D grid of cells."""

    model_config = ConfigDict(extra="ignore")

    id: str
    index: int
    block_type: BlockType = BlockType.TABLE
    rows: int = 0
    columns: int = 0
    style_id: str | None = None
    style_name: str | None = None
    width_twips: int | None = None
    alignment: str | None = None
    grid: list[list[CellInfo]] = []  # grid[row][col]

    def flat_cells(self) -> list[CellInfo]:
        return [cell for row in self.grid for cell in row]

    def first_row_texts(self) -> list[str]:
        return [c.text for c in self.grid[0]] if self.grid else []


class SectionBoundary(BaseModel):
    """Marks a section break (``<w:sectPr>``) in document order."""

    model_config = ConfigDict(extra="ignore")

    id: str
    index: int
    block_type: BlockType = BlockType.SECTION_BOUNDARY
    section: SectionMeta = SectionMeta(id="sec-000000", index=0)


DocumentBlock = ParagraphBlock | TableBlock | SectionBoundary
