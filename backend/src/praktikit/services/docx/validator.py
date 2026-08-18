"""Secure input validation for uploaded/source DOCX files (spec Section 10/11).

Validation happens **before** any parsing. We never trust the file extension:
we check the ZIP signature, required OOXML parts, size limits, and reject
encrypted/suspicious packages. The original file is treated as untrusted input.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

from praktikit.core.config import get_settings
from praktikit.core.exceptions import DocxValidationError, UnsupportedFormatError

ZIP_SIGNATURE = b"PK\x03\x04"
ZIP_EMPTY_SIGNATURE = b"PK\x05\x06"  # empty archive signature
CONTENT_TYPES_PART = "[Content_Types].xml"
DOCUMENT_PART = "word/document.xml"
ENCRYPTION_PART = "EncryptionInfo"

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SUPPORTED_EXTENSIONS = {".docx"}


def validate_extension(path: Path) -> None:
    """Reject unsupported formats up front (spec: .docx first-class; .doc/.pdf later)."""
    ext = path.suffix.lower()
    if ext == ".doc":
        raise UnsupportedFormatError(
            "Format .doc (Word lama) belum didukung. Silakan konversi ke .docx terlebih dahulu."
        )
    if ext == ".pdf":
        raise UnsupportedFormatError("PDF belum didukung (eksperimental). Gunakan file .docx.")
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"Ekstensi '{ext}' tidak didukung. Hanya file .docx yang diterima."
        )


def validate_size(path: Path) -> None:
    """Reject files larger than the configured maximum."""
    max_size = get_settings().max_upload_size
    size = path.stat().st_size
    if size <= 0:
        raise DocxValidationError("File kosong (0 byte).")
    if size > max_size:
        raise DocxValidationError(
            f"Ukuran file terlalu besar ({size} bytes). Maksimum {max_size} bytes."
        )


def read_zip_signature(path: Path, n: int = 4) -> bytes:
    """Read the first ``n`` bytes of ``path`` for signature sniffing."""
    with open(path, "rb") as fh:
        return fh.read(n)


def is_zip_file(path: Path) -> bool:
    """True when the file starts with a ZIP local-file-header signature."""
    sig = read_zip_signature(path, len(ZIP_SIGNATURE))
    return sig == ZIP_SIGNATURE


def assert_safe_zip_entries(zf: zipfile.ZipFile) -> None:
    """Reject zip entries that attempt path traversal or use unsafe characters.

    Guards against zip-slip attacks (spec Section 11): no absolute paths, no
    ``..`` components, and no backslashes that could escape on Windows.
    """
    for info in zf.infolist():
        name = info.filename
        if name.startswith("/") or name.startswith("\\"):
            raise DocxValidationError(f"Entri zip dengan path absolute terdeteksi: {name!r}")
        if ".." in name.replace("\\", "/").split("/"):
            raise DocxValidationError(f"Path traversal terdeteksi pada entri zip: {name!r}")
        # NUL bytes / control chars are not valid in OOXML part names.
        if any(ord(c) < 32 for c in name):
            raise DocxValidationError(f"Karakter ilegal pada nama entri zip: {name!r}")


def validate_docx_file(path: str | os.PathLike) -> Path:
    """Run the full input validation suite and return a :class:`Path`.

    Raises :class:`UnsupportedFormatError` for wrong formats and
    :class:`DocxValidationError` for corrupt/untrustworthy packages.
    """
    p = Path(path)
    if not p.exists():
        raise DocxValidationError(f"File tidak ditemukan: {p}")
    if not p.is_file():
        raise DocxValidationError(f"Bukan file biasa: {p}")

    validate_extension(p)
    validate_size(p)

    if not is_zip_file(p):
        raise DocxValidationError(
            "File tidak memiliki signature ZIP yang valid — bukan file .docx sebenarnya."
        )

    try:
        with zipfile.ZipFile(p, "r") as zf:
            assert_safe_zip_entries(zf)
            names = set(zf.namelist())
    except zipfile.BadZipFile as exc:
        raise DocxValidationError(f"File ZIP rusak atau tidak dapat dibaca: {exc}") from exc

    # Encrypted OOXML packages expose EncryptionInfo instead of [Content_Types].xml.
    if ENCRYPTION_PART in names and CONTENT_TYPES_PART not in names:
        raise DocxValidationError(
            "File tampaknya terenkripsi / password-protected dan tidak dapat diproses."
        )

    if CONTENT_TYPES_PART not in names:
        raise DocxValidationError("Package tidak memiliki '[Content_Types].xml' yang wajib ada.")
    if DOCUMENT_PART not in names:
        raise DocxValidationError(
            "Package tidak memiliki 'word/document.xml' — bukan dokumen Word yang valid."
        )

    return p
