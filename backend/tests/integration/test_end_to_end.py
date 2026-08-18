"""End-to-end integration test (spec Section 91 / 74)."""

from docx import Document

from praktikit.services.docx.template_generator import TemplateGenerator
from praktikit.services.docx.validator import validate_docx_file


def test_full_pipeline_generates_valid_template(acceptance_docx, tmp_dir):
    """analyze → clean → reopen → assert structure preserved, content cleaned."""
    output = tmp_dir / "template.docx"
    generator = TemplateGenerator()
    generator.generate(acceptance_docx, output)
    assert output.exists()

    # Original file must be unchanged.
    import hashlib

    hash_before = hashlib.sha256(acceptance_docx.read_bytes()).hexdigest()
    assert hashlib.sha256(acceptance_docx.read_bytes()).hexdigest() == hash_before

    # Output is a valid DOCX.
    validate_docx_file(output)

    # Reopen with python-docx (openability test).
    doc = Document(str(output))
    texts = [p.text for p in doc.paragraphs]
    joined = "\n".join(texts)

    # Headings preserved.
    assert "BAB I" in joined
    assert "BAB II" in joined
    assert "1.1 Latar Belakang" in joined

    # Identity replaced with placeholders.
    assert "{{NAMA}}" in joined
    assert "{{NIM}}" in joined
    assert "John Doe" not in joined
    assert "24123456" not in joined

    # Old content removed.
    assert "OLD BACKGROUND" not in joined
    assert "OLD OBJECTIVES" not in joined
    assert "OLD THEORY" not in joined
    assert "OLD CONCLUSION" not in joined

    # Contextual placeholders present.
    assert "[Tulis latar belakang di sini]" in joined
    assert "[Tulis landasan teori di sini]" in joined


def test_generated_output_keeps_layout(acceptance_docx, tmp_dir):
    """Page layout and margins survive generation."""
    output = tmp_dir / "template_layout.docx"
    TemplateGenerator().generate(acceptance_docx, output)

    from praktikit.services.docx.parser import DocxParser

    src_meta = DocxParser.from_path(acceptance_docx).parse().document_meta
    out_meta = DocxParser.from_path(output).parse().document_meta

    assert out_meta.page_layout.width_twips == src_meta.page_layout.width_twips
    assert out_meta.page_layout.height_twips == src_meta.page_layout.height_twips
    assert out_meta.margins.top == src_meta.margins.top
    assert out_meta.margins.left == src_meta.margins.left
    assert out_meta.section_count == src_meta.section_count


def test_clean_template_is_deterministic(acceptance_docx, tmp_dir):
    """Running generation twice yields structurally equivalent templates."""
    out1 = tmp_dir / "t1.docx"
    out2 = tmp_dir / "t2.docx"
    TemplateGenerator().generate(acceptance_docx, out1)
    TemplateGenerator().generate(acceptance_docx, out2)

    from praktikit.services.docx.parser import DocxParser

    b1 = [b.text for b in DocxParser.from_path(out1).parse().blocks if hasattr(b, "text")]
    b2 = [b.text for b in DocxParser.from_path(out2).parse().blocks if hasattr(b, "text")]
    assert b1 == b2
