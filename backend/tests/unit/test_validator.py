"""Unit tests: input validation (spec Section 10)."""


import pytest

from praktikit.core.exceptions import DocxValidationError, UnsupportedFormatError
from praktikit.services.docx.validator import validate_docx_file


def test_accepts_valid_docx(acceptance_docx):
    """Valid DOCX is accepted."""
    p = validate_docx_file(acceptance_docx)
    assert p.exists()
    assert p.suffix == ".docx"


def test_rejects_non_zip(tmp_dir):
    """Non-ZIP files are rejected."""
    bad = tmp_dir / "notazip.docx"
    bad.write_text("hello not a docx")
    with pytest.raises(DocxValidationError):
        validate_docx_file(bad)


def test_rejects_empty(tmp_dir):
    """Empty files are rejected."""
    bad = tmp_dir / "empty.docx"
    bad.write_bytes(b"PK\x03\x04")  # fake ZIP header
    with pytest.raises(DocxValidationError):
        validate_docx_file(bad)


def test_rejects_encrypted(tmp_dir):
    """Encrypted packages are rejected."""
    bad = tmp_dir / "encrypted.docx"
    # Simulate encrypted by writing a fake DOCX without [Content_Types].xml
    import zipfile
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("EncryptionInfo", "fake")
    with pytest.raises(DocxValidationError):
        validate_docx_file(bad)


def test_rejects_doc_format(tmp_dir):
    """Legacy .doc format is rejected."""
    bad = tmp_dir / "old.doc"
    bad.write_text("fake .doc")
    with pytest.raises(UnsupportedFormatError):
        validate_docx_file(bad)


def test_rejects_pdf(tmp_dir):
    """PDF format is rejected."""
    bad = tmp_dir / "a.pdf"
    bad.write_bytes(b"%PDF-1.4")
    with pytest.raises(UnsupportedFormatError):
        validate_docx_file(bad)


def test_rejects_too_large(tmp_dir, monkeypatch):
    """Files over the configured size limit are rejected."""
    big = tmp_dir / "big.docx"
    big.write_bytes(b"PK\x03\x04" + b"x" * (30 * 1024 * 1024))  # 30 MB
    monkeypatch.setenv("MAX_UPLOAD_SIZE", str(25 * 1024 * 1024))
    from praktikit.core.config import reset_settings
    reset_settings()
    with pytest.raises(DocxValidationError):
        validate_docx_file(big)
