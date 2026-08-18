"""Unit tests: detection pipeline (structure, variables, cleaning plan)."""

from praktikit.services.docx.cleaning_planner import CleaningPlanner
from praktikit.services.docx.parser import DocxParser
from praktikit.services.docx.semantic_classifier import HeuristicSemanticClassifier
from praktikit.services.docx.structure_detector import StructureDetector
from praktikit.services.docx.variable_detector import VariableDetector


def _run_pipeline(docx_path):
    parse = DocxParser.from_path(docx_path).parse()
    sd = StructureDetector(parse.blocks, parse.styles_by_id).detect()
    cls = HeuristicSemanticClassifier().classify_all(
        parse.blocks, sd.heading_info, sd.structure_tree, sd.cover_end_index
    )
    vars_ = VariableDetector().detect(parse.blocks, cls, sd.cover_end_index)
    plan = CleaningPlanner().build(
        parse.blocks, sd.heading_info, cls, vars_, sd.cover_end_index
    )
    return parse, sd, cls, vars_, plan


def test_detects_bab_headings(acceptance_docx):
    """BAB I, BAB II, ... are detected as major headings."""
    parse, sd, cls, vars_, plan = _run_pipeline(acceptance_docx)
    major = [h for h in sd.heading_info if h.level == 0]
    titles = [h.title for h in major]
    assert "BAB I" in titles
    assert "BAB II" in titles
    assert "BAB III" in titles
    assert "BAB IV" in titles


def test_detects_subheadings(acceptance_docx):
    """1.1, 1.2 style subheadings are detected."""
    parse, sd, cls, vars_, plan = _run_pipeline(acceptance_docx)
    sub = [h for h in sd.heading_info if h.level == 2]
    titles = [h.title.lower() for h in sub]
    assert any("latar" in t for t in titles)
    assert any("tujuan" in t for t in titles)


def test_detects_variables(acceptance_docx):
    """Identity variables (Nama, NIM) are detected."""
    parse, sd, cls, vars_, plan = _run_pipeline(acceptance_docx)
    labels = [v.label.lower() for v in vars_]
    assert "nama" in labels
    assert "nim" in labels
    # Placeholders are standard.
    for v in vars_:
        if v.label.lower() == "nama":
            assert v.placeholder == "{{NAMA}}"
        if v.label.lower() == "nim":
            assert v.placeholder == "{{NIM}}"


def test_cleaning_plan_clears_body(acceptance_docx):
    """Body content blocks get KEEP_STRUCTURE_CLEAR_CONTENT."""
    parse, sd, cls, vars_, plan = _run_pipeline(acceptance_docx)
    from praktikit.models.cleaning import CleaningAction

    # Find the old background paragraph.
    old_bg_block = None
    for b in parse.blocks:
        if hasattr(b, "text") and "OLD BACKGROUND" in b.text:
            old_bg_block = b
            break
    assert old_bg_block is not None
    # Its operation should be clear_content.
    ops = [op for op in plan.operations if op.target == old_bg_block.id]
    assert ops
    assert ops[0].action == CleaningAction.KEEP_STRUCTURE_CLEAR_CONTENT
    assert "latar" in (ops[0].placeholder or "").lower()


def test_cleaning_plan_replaces_variables(acceptance_docx):
    """Variable blocks get REPLACE_WITH_PLACEHOLDER."""
    parse, sd, cls, vars_, plan = _run_pipeline(acceptance_docx)
    from praktikit.models.cleaning import CleaningAction

    var_ids = {v.block_id for v in vars_}
    for op in plan.operations:
        if op.target in var_ids:
            assert op.action == CleaningAction.REPLACE_WITH_PLACEHOLDER
            assert op.placeholder is not None


def test_custom_headings_detected(custom_heading_docx):
    """I., A., B. style headings are detected even without Word styles."""
    parse, sd, cls, vars_, plan = _run_pipeline(custom_heading_docx)
    titles = [h.title.upper() for h in sd.heading_info]
    # At least one major heading should be detected.
    assert any("PENDAHULUAN" in t for t in titles)


def test_table_identity_detection(table_docx):
    """Identity tables produce variables, data tables produce CLEAR_TABLE_DATA."""
    parse, sd, cls, vars_, plan = _run_pipeline(table_docx)
    # Variables from the identity table.
    labels = [v.label.lower() for v in vars_]
    assert "nama" in labels
    assert "nim" in labels
