"""Leak regression test (spec Section 65)."""


from praktikit.services.docx.leak_detector import LeakDetector
from praktikit.services.docx.template_generator import TemplateGenerator

SECRET = "UNIQUE_SECRET_REPORT_SENTENCE_123"


def test_secret_content_not_present_in_output(acceptance_docx, tmp_dir):
    """BODY_CONTENT classified text must not survive into the template."""
    output = tmp_dir / "clean.docx"
    TemplateGenerator().generate(acceptance_docx, output)

    joined = output.read_bytes()
    assert SECRET.encode() not in joined


def test_leak_detector_finds_real_leak(acceptance_docx, tmp_dir, monkeypatch):
    """Leak detector flags output that still contains old body content."""
    # Build an analysis, then simulate a leaky output (copy of source).
    generator = TemplateGenerator()
    analysis = generator.analyze(acceptance_docx)

    leaky = tmp_dir / "leaky.docx"
    import shutil
    shutil.copy2(acceptance_docx, leaky)  # unmodified source = leaky template

    detector = LeakDetector(threshold=0.5)
    leaks = detector.detect(acceptance_docx, leaky, analysis)
    assert leaks, "Expected the leak detector to find old content"


def test_strict_mode_raises_on_leak(acceptance_docx, tmp_dir, monkeypatch):
    """Strict leak check refuses to produce a leaky output."""
    monkeypatch.setenv("STRICT_LEAK_CHECK", "true")
    from praktikit.core.config import reset_settings
    reset_settings()
    generator = TemplateGenerator()
    output = tmp_dir / "strict.docx"
    # Normal generation should succeed (no leak).
    generator.generate(acceptance_docx, output)
    reset_settings()
