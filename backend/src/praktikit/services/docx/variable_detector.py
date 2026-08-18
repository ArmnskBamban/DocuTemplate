"""Identity variable detection (spec Section 17/18).

Detects personal/identity fields (Nama, NIM, Kelas, …) that should be replaced
with placeholders. Supports three layout patterns:

- **Inline**: ``Nama : John Doe`` on a single paragraph.
- **Stacked**: ``Nama`` on one paragraph, ``John Doe`` on the next.
- **Table**: two-column table with label column and value column.

Detected variables are mapped to standard placeholders; unknown fields get
generic ``{{FIELD_n}}`` placeholders the user can rename.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from praktikit.models.blocks import ParagraphBlock, TableBlock
from praktikit.models.variables import VariableField
from praktikit.utils.text import normalize, split_label_value

if TYPE_CHECKING:
    from praktikit.models.blocks import DocumentBlock
    from praktikit.models.classification import Classification

# Standard identity labels (Indonesian + English) and their placeholder names.
_STANDARD_FIELDS: dict[str, str] = {
    # Indonesian
    "nama": "NAMA",
    "nim": "NIM",
    "npm": "NIM",
    "nrp": "NIM",
    "kelas": "KELAS",
    "kelompok": "KELOMPOK",
    "program studi": "PROGRAM_STUDI",
    "prodi": "PROGRAM_STUDI",
    "jurusan": "JURUSAN",
    "semester": "SEMESTER",
    "tahun akademik": "TAHUN_AKADEMIK",
    "mata kuliah": "MATA_KULIAH",
    "mata kuliah / mata kuliah": "MATA_KULIAH",
    "modul": "NOMOR_MODUL",
    "nomor modul": "NOMOR_MODUL",
    "judul": "JUDUL_MODUL",
    "judul modul": "JUDUL_MODUL",
    "asisten": "ASISTEN",
    "nama asisten": "ASISTEN",
    "dosen": "DOSEN",
    "nama dosen": "DOSEN",
    "tanggal": "TANGGAL",
    "tgl": "TANGGAL",
    "hari": "HARI",
    "waktu": "WAKTU",
    "ruangan": "RUANGAN",
    "praktikum": "MATA_KULIAH",
    # English variants
    "name": "NAMA",
    "student id": "NIM",
    "student number": "NIM",
    "class": "KELAS",
    "course": "MATA_KULIAH",
    "module": "NOMOR_MODUL",
    "title": "JUDUL_MODUL",
    "assistant": "ASISTEN",
    "lecturer": "DOSEN",
    "instructor": "DOSEN",
    "date": "TANGGAL",
}

# Inverted for fast lookup: normalized + lowercased label → placeholder.
_FIELD_LOOKUP: dict[str, str] = {normalize(k).lower(): v for k, v in _STANDARD_FIELDS.items()}


def _lookup_placeholder(label: str) -> str | None:
    """Map a label to a standard placeholder, or return None."""
    return _FIELD_LOOKUP.get(normalize(label).lower())


class VariableDetector:
    """Detect identity fields across the three supported patterns."""

    def __init__(self):
        self._var_counter = 0

    def detect(
        self,
        blocks: list[DocumentBlock],
        classifications: dict[str, Classification],
        cover_end_index: int,
    ) -> list[VariableField]:
        variables: list[VariableField] = []
        # Inline patterns (single paragraph with Label : Value).
        variables.extend(self._detect_inline(blocks, classifications, cover_end_index))
        # Table identity patterns.
        variables.extend(self._detect_table(blocks, classifications))
        # Stacked patterns (Label paragraph followed by Value paragraph).
        variables.extend(self._detect_stacked(blocks, classifications, cover_end_index))
        return variables

    def _next_id(self) -> str:
        self._var_counter += 1
        return f"v-{self._var_counter:06d}"

    def _detect_inline(
        self,
        blocks: list[DocumentBlock],
        classifications: dict[str, Classification],
        cover_end_index: int,
    ) -> list[VariableField]:
        results: list[VariableField] = []
        for b in blocks:
            if not isinstance(b, ParagraphBlock):
                continue
            if b.is_blank:
                continue
            # Focus on cover region and COVER_VARIABLE-classified blocks.
            clf = classifications.get(b.id)
            if clf and clf.role.value not in ("cover_variable", "cover_static", "blank", "unknown"):
                continue
            m = split_label_value(b.text)
            if m is None:
                continue
            label, value = m
            ph = _lookup_placeholder(label)
            standard = ph is not None
            if ph is None:
                ph = f"FIELD_{self._var_counter + 1}"
            results.append(
                VariableField(
                    id=self._next_id(),
                    block_id=b.id,
                    label=label,
                    original_value=value,
                    placeholder=f"{{{{{ph}}}}}",
                    standard=standard,
                    location="inline",
                )
            )
        return results

    def _detect_table(
        self,
        blocks: list[DocumentBlock],
        classifications: dict[str, Classification],
    ) -> list[VariableField]:
        results: list[VariableField] = []
        for b in blocks:
            if not isinstance(b, TableBlock):
                continue
            clf = classifications.get(b.id)
            if clf is None or clf.role.value != "table_identity":
                continue
            for row_idx, row in enumerate(b.grid):
                if len(row) >= 2:
                    label_cell = row[0]
                    value_cell = row[1]
                    label = label_cell.text.strip()
                    value = value_cell.text.strip()
                    if not label or not value:
                        continue
                    ph = _lookup_placeholder(label)
                    standard = ph is not None
                    if ph is None:
                        ph = f"FIELD_{self._var_counter + 1}"
                    results.append(
                        VariableField(
                            id=self._next_id(),
                            block_id=b.id,
                            label=label,
                            original_value=value,
                            placeholder=f"{{{{{ph}}}}}",
                            standard=standard,
                            location="table",
                            cell=(row_idx, 1),
                        )
                    )
        return results

    def _detect_stacked(
        self,
        blocks: list[DocumentBlock],
        classifications: dict[str, Classification],
        cover_end_index: int,
    ) -> list[VariableField]:
        """Detect label on one paragraph, value on the next (in cover region)."""
        results: list[VariableField] = []
        paras = [b for b in blocks if isinstance(b, ParagraphBlock) and not b.is_blank and b.index < cover_end_index]
        skip: set[str] = set()  # blocks already consumed by inline detection

        # Collect ids from inline detection to avoid double-counting.
        for b in blocks:
            if isinstance(b, ParagraphBlock) and not b.is_blank:
                if split_label_value(b.text) is not None:
                    skip.add(b.id)

        for i in range(len(paras) - 1):
            label_p = paras[i]
            value_p = paras[i + 1]
            if label_p.id in skip or value_p.id in skip:
                continue
            label = label_p.text.strip()
            value = value_p.text.strip()
            ph = _lookup_placeholder(label)
            if ph is None:
                continue
            # Verify value looks like a value (not another label).
            if split_label_value(value) is not None:
                continue
            results.append(
                VariableField(
                    id=self._next_id(),
                    block_id=value_p.id,
                    label=label,
                    original_value=value,
                    placeholder=f"{{{{{ph}}}}}",
                    standard=True,
                    location="stacked",
                )
            )
            skip.add(label_p.id)
            skip.add(value_p.id)
        return results
