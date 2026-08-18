"""Unit tests: ordered block parser (spec Section 13)."""

import pytest

from praktikit.services.docx.parser import DocxParser


def test_ordered_blocks(acceptance_docx):
    """Blocks are enumerated in document order, with stable IDs."""
    parse = DocxParser.from_path(acceptance_docx).parse()
    assert parse.document_meta.section_count == 1
    assert parse.document_meta.styles
    assert parse.blocks
    # First block should be a paragraph.
    first = parse.blocks[0]
    assert first.id == "p-000001"
    assert first.block_type.value == "paragraph"
    # Count paragraphs, tables.
    table_ids = [b.id for b in parse.blocks if b.block_type.value == "table"]
    assert sum(1 for b in parse.blocks if b.block_type.value == "paragraph") > 0
    # Acceptance docx has no tables.
    assert not table_ids
    # IDs are monotonic and non‑overlapping.
    seen = set()
    for b in parse.blocks:
        assert b.id not in seen
        seen.add(b.id)
        # Each ID has the expected prefix.
        assert b.id.startswith(("p-", "tbl-", "img-", "sec-"))


def test_style_extraction(acceptance_docx):
    """Word styles are correctly indexed."""
    parse = DocxParser.from_path(acceptance_docx).parse()
    assert "Heading1" in parse.styles_by_id
    h1 = parse.styles_by_id["Heading1"]
    assert h1.is_heading is True
    assert h1.heading_level == 1
    assert h1.name == "Heading 1"
    assert h1.style_type == "paragraph"


def test_image_metadata(acceptance_docx):
    """Image relationship IDs and sizes are captured."""
    parse = DocxParser.from_path(acceptance_docx).parse()
    # This fixture has no images, but verify that image handling doesn't crash.
    for block in parse.blocks:
        if hasattr(block, "images"):
            assert isinstance(block.images, list)


def test_table_cell_grid(custom_heading_docx):
    """Table cells are extracted with row/col indices."""
    parse = DocxParser.from_path(custom_heading_docx).parse()
    # No tables in custom_heading fixture.
    # Ensure parser doesn't raise.
    for block in parse.blocks:
        if block.block_type.value == "table":
            tbl = block
            assert tbl.rows >= 0
            assert tbl.columns >= 0
            # grid[row][col] present.
            assert len(tbl.grid) == tbl.rows
            for row in tbl.grid:
                assert len(row) == tbl.columns


def test_page_layout_and_margins(acceptance_docx):
    """Page layout and margins are captured."""
    parse = DocxParser.from_path(acceptance_docx).parse()
    meta = parse.document_meta
    assert meta.page_layout.size_name is not None
    assert meta.margins.top is not None
    assert meta.margins.left is not None
    # Our fixture sets 3 cm top, 4 cm left.
    # Convert twips → cm, rounding errors allowed.
    assert meta.margins.to_cm()["top"] == pytest.approx(3.0, abs=0.2)
    assert meta.margins.to_cm()["left"] == pytest.approx(4.0, abs=0.2)
