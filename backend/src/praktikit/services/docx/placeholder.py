"""Contextual placeholder generation (spec Section 21).

Maps a heading (or nearby section title) to a natural-language placeholder
without using any LLM. Indonesian academic text is the primary audience; a
generic fallback handles unknown headings.
"""

from __future__ import annotations

import re

# Heading title (normalized, lowercased) → placeholder template.
_PLACEHOLDER_MAP: dict[str, str] = {
    "latar belakang": "[Tulis latar belakang di sini]",
    "landasan teori": "[Tulis landasan teori di sini]",
    "dasar teori": "[Tulis dasar teori di sini]",
    "tinjauan pustaka": "[Tulis tinjauan pustaka di sini]",
    "tujuan": "[Tuliskan tujuan praktikum]",
    "rumusan masalah": "[Tuliskan rumusan masalah]",
    "metode": "[Tuliskan metode yang digunakan]",
    "metodologi": "[Tuliskan metodologi yang digunakan]",
    "alat dan bahan": "[Masukkan alat dan bahan]",
    "langkah kerja": "[Masukkan langkah kerja]",
    "prosedur": "[Masukkan prosedur percobaan]",
    "hasil": "[Masukkan hasil praktikum di sini]",
    "hasil dan pembahasan": "[Masukkan hasil dan pembahasan di sini]",
    "hasil percobaan": "[Masukkan hasil percobaan di sini]",
    "analisis": "[Isi analisis di sini]",
    "pembahasan": "[Jelaskan hasil praktikum di sini]",
    "analisis dan pembahasan": "[Jelaskan analisis dan pembahasan]",
    "kesimpulan": "[Tuliskan kesimpulan]",
    "penutup": "[Tuliskan penutup]",
    "saran": "[Tuliskan saran]",
    "daftar pustaka": "[Tambahkan referensi]",
    "referensi": "[Tambahkan referensi]",
    "lampiran": "[Tambahkan lampiran]",
    "pelaksanaan": "[Masukkan langkah pelaksanaan]",
    "data pengamatan": "[Masukkan data pengamatan]",
    "pengujian": "[Masukkan hasil pengujian]",
}

# Simple title cleaning for fallback: remove numbering prefix.
# Match numbering prefixes like "1.", "1.1 ", "I. ", "A. ", "BAB I ", but NOT "LAPORAN"
_NUMBER_PREFIX_RE = re.compile(r"^\s*(?:BAB\s+[IVXLCDM]+|CHAPTER\s+[IVXLCDM\d]+|\d+(?:\.\d+)*|[IVXLCDM]+|[A-Z])[\.\s)]+\s*")


def placeholder_for_heading(title: str) -> str:
    """Return a contextual placeholder for a section heading's title."""
    if not title:
        return "[Isi di sini]"
    key = _clean_title(title)
    if key in _PLACEHOLDER_MAP:
        return _PLACEHOLDER_MAP[key]
    # Fallback: "[Isi {Title} di sini]"
    cleaned = _clean_title_for_display(title)
    return f"[Isi {cleaned} di sini]"


def _clean_title(title: str) -> str:
    """Normalize for map lookup."""
    from praktikit.utils.text import normalize

    return normalize(title).lower().strip()


def _clean_title_for_display(title: str) -> str:
    """Remove numbering prefix for display but keep casing."""
    cleaned = _NUMBER_PREFIX_RE.sub("", title).strip()
    return cleaned or title
