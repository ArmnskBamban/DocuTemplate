"""Heuristic semantic classifier (spec Section 15/46).

Assigns a :class:`SemanticRole` + confidence to each document block, using
structural position, heading detection results, text content, and formatting.
This is the **baseline classifier** — fully deterministic, no LLM required.
An LLM-based classifier is defined as a future ``Protocol`` extension (Section 46).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol

from praktikit.core.config import get_settings
from praktikit.models.blocks import ParagraphBlock, TableBlock
from praktikit.models.classification import (
    Automation,
    Classification,
    SemanticRole,
    automation_for_confidence,
)
from praktikit.models.structure import HeadingInfo, StructureNode

if TYPE_CHECKING:
    from praktikit.models.blocks import DocumentBlock

# -- text signal helpers --

_CAPTION_RE = re.compile(r"^\s*(?:gambar|tabel|figure|table|grafik|diagram)\s*\d", re.IGNORECASE)
_REFERENCES_RE = re.compile(
    r"^\s*(?:daftar\s+pustaka|referensi|references|bibliography|sumber|daftar\s+referensi)",
    re.IGNORECASE,
)
_APPENDIX_RE = re.compile(r"^\s*(?:lampiran|appendix|lampiran\s+\w)", re.IGNORECASE)
_BODY_START_RE = re.compile(
    r"^\s*(?:1\.|a\.|i\.|[A-I]\.|pertama|kedua|langkah|prosedur|hasil|analisis|"
    r"pembahasan|kesimpulan|perkembangan|teknologi|sistem|data|menggunakan|"
    r"berdasarkan|penelitian|pengetahuan|jaringan|operasi|metode|maka|oleh|"
    r"menunjukkan|merupakan|adalah|mempunyai|memiliki|dapat|untuk|melakukan|"
    r"melalui|sebagai|yaitu|yang|dengan|pada|di|secara)",
    re.IGNORECASE,
)

# Cover static keywords (Indonesian / generic academic)
_COVER_KEYWORDS = {
    "universitas", "fakultas", "program studi", "jurusan",
    "laporan", "praktikum", "laboratorium", "lab",
    "disusun oleh", "disusun oleh:", "oleh", "asisten",
}


class SemanticClassifier(Protocol):
    """Protocol for pluggable classifiers (heuristic or future LLM)."""

    def classify_all(
        self,
        blocks: list[DocumentBlock],
        headings: list[HeadingInfo],
        structure_tree: list[StructureNode],
        cover_end_index: int,
    ) -> dict[str, Classification]: ...


class HeuristicSemanticClassifier:
    """Deterministic baseline classifier — no external dependencies."""

    def classify_all(
        self,
        blocks: list[DocumentBlock],
        headings: list[HeadingInfo],
        structure_tree: list[StructureNode],
        cover_end_index: int,
    ) -> dict[str, Classification]:
        settings = get_settings()
        heading_ids = {h.block_id: h for h in headings}
        cover_node = self._find_cover_node(structure_tree)
        variable_blocks = self._identify_variable_blocks(blocks, cover_end_index)
        references_blocks = self._find_references_heading(blocks)
        appendix_blocks = self._find_appendix_heading(blocks)

        results: dict[str, Classification] = {}
        for block in blocks:
            clf = self._classify(
                block, heading_ids, cover_end_index, cover_node,
                variable_blocks, references_blocks, appendix_blocks,
                settings.auto_threshold, settings.review_threshold,
            )
            results[block.id] = clf
        return results

    def _classify(
        self, block, heading_ids, cover_end_index, cover_node,
        variable_blocks, references_blocks, appendix_blocks,
        auto_thresh, review_thresh,
    ) -> Classification:
        text = getattr(block, "text", "").strip()
        idx = getattr(block, "index", 0)

        # --- chapter / section heading ---
        if block.id in heading_ids:
            h = heading_ids[block.id]
            if h.level == 0:
                role = SemanticRole.CHAPTER_HEADING
            elif h.level == 1:
                role = SemanticRole.SECTION_HEADING
            else:
                role = SemanticRole.SUBSECTION_HEADING
            conf = h.confidence
            reasons = list(h.reasons)
            auto = automation_for_confidence(conf, auto_thresh, review_thresh)
            return Classification(
                block_id=block.id, role=role, confidence=conf,
                reasons=reasons, automation=auto,
            )

        # --- blank paragraphs ---
        if isinstance(block, ParagraphBlock) and not text:
            auto = Automation.KEEP
            return Classification(
                block_id=block.id, role=SemanticRole.BLANK,
                confidence=0.95, reasons=["blank_paragraph"], automation=auto,
            )

        # --- cover region ---
        if isinstance(block, ParagraphBlock) and idx < cover_end_index:
            if block.id in variable_blocks:
                return Classification(
                    block_id=block.id, role=SemanticRole.COVER_VARIABLE,
                    confidence=0.80, reasons=["cover_identity"], automation=Automation.REVIEW,
                )
            # Static cover text detection.
            if self._is_cover_static(text):
                return Classification(
                    block_id=block.id, role=SemanticRole.COVER_STATIC,
                    confidence=0.85, reasons=["cover_static_keyword"], automation=Automation.AUTO,
                )
            # In cover, centered short text → likely static.
            props = block.props
            if props.alignment == "center" and len(text.split()) <= 6:
                return Classification(
                    block_id=block.id, role=SemanticRole.COVER_STATIC,
                    confidence=0.70, reasons=["cover_centered_short"], automation=Automation.REVIEW,
                )
            # Cover image detection (image in cover region → likely logo).
            if props.contains_image:
                return Classification(
                    block_id=block.id, role=SemanticRole.IMAGE_LOGO,
                    confidence=0.75, reasons=["cover_image"], automation=Automation.REVIEW,
                )
            # Fallback in cover: keep with low confidence.
            return Classification(
                block_id=block.id, role=SemanticRole.COVER_STATIC,
                confidence=0.50, reasons=["cover_unknown"], automation=Automation.KEEP,
            )

        # --- references heading ---
        if block.id in references_blocks:
            return Classification(
                block_id=block.id, role=SemanticRole.REFERENCES_HEADING,
                confidence=0.90, reasons=["references_pattern"], automation=Automation.AUTO,
            )

        # --- appendix heading ---
        if block.id in appendix_blocks:
            return Classification(
                block_id=block.id, role=SemanticRole.APPENDIX_HEADING,
                confidence=0.90, reasons=["appendix_pattern"], automation=Automation.AUTO,
            )

        # --- table ---
        if isinstance(block, TableBlock):
            return self._classify_table(block, idx, heading_ids, auto_thresh, review_thresh)

        # --- paragraph: content, caption, etc. ---
        return self._classify_paragraph(
            block, heading_ids, auto_thresh, review_thresh
        )

    def _classify_table(self, block: TableBlock, idx, heading_ids, auto_thresh, review_thresh) -> Classification:
        # Identity table (2 cols, label-like first column).
        if block.rows == 1 and block.columns == 1:
            return Classification(
                block_id=block.id, role=SemanticRole.TABLE_IDENTITY,
                confidence=0.80, reasons=["single_cell_identity"], automation=Automation.REVIEW,
            )
        if block.columns == 2 and block.rows <= 6:
            first_col = [block.grid[r][0].text.strip() for r in range(block.rows)]
            if any(self._is_label_like(t) for t in first_col if t):
                return Classification(
                    block_id=block.id, role=SemanticRole.TABLE_IDENTITY,
                    confidence=0.85, reasons=["two_col_label_value"], automation=Automation.REVIEW,
                )
        # Template/result table.
        if block.rows >= 2:
            return Classification(
                block_id=block.id, role=SemanticRole.TABLE_CONTENT,
                confidence=0.75, reasons=["data_table"], automation=Automation.REVIEW,
            )
        return Classification(
            block_id=block.id, role=SemanticRole.TABLE_TEMPLATE,
            confidence=0.60, reasons=["table_unknown"], automation=Automation.KEEP,
        )

    def _classify_paragraph(self, block: ParagraphBlock, heading_ids, auto_thresh, review_thresh) -> Classification:
        text = block.text.strip()
        # Caption.
        if _CAPTION_RE.match(text):
            return Classification(
                block_id=block.id, role=SemanticRole.CAPTION,
                confidence=0.90, reasons=["caption_pattern"], automation=Automation.AUTO,
            )
        # Image in body → content image.
        if block.props.contains_image:
            return Classification(
                block_id=block.id, role=SemanticRole.IMAGE_CONTENT,
                confidence=0.75, reasons=["body_image"], automation=Automation.REVIEW,
            )
        # Page-break-only paragraph.
        if block.props.contains_page_break and not text:
            return Classification(
                block_id=block.id, role=SemanticRole.PAGE_BREAK,
                confidence=0.95, reasons=["page_break"], automation=Automation.AUTO,
            )
        # List items (a), b), c), 1), 2), 10), AA), A), B), etc.) → instruction text to remove.
        # Match patterns: "a) text", "1) text", "10) text", "A) text", "a. text", etc.
        # BUT exclude heading patterns like "2.3", "1.1", "2.3.1" (those are subsection headings)
        list_item_pattern = r"^\s*[a-zA-Z0-9]{1,2}[\)\.]\s*\S"
        heading_pattern = r"^\s*\d+(\.\d+)+\s"
        is_list_item = re.match(list_item_pattern, text)
        is_heading = re.match(heading_pattern, text)
        if is_list_item and not is_heading:
            return Classification(
                block_id=block.id, role=SemanticRole.INSTRUCTION_TEXT,
                confidence=0.85, reasons=["list_item_pattern"], automation=Automation.AUTO,
            )
        # Likely body content: any non-blank paragraph in the body region that is
        # not a heading/caption/image/break is content that must be cleared.
        # Confidence scales with text length; even terse lines (e.g. "OLD THEORY")
        # are body content with enough confidence to clean (flagged for review).
        if len(text) > 30:
            conf = 0.90
            reasons = ["body_text"]
        elif len(text) >= 8:
            conf = 0.82
            reasons = ["body_short_text"]
        else:
            conf = 0.75
            reasons = ["body_terse"]
        auto = automation_for_confidence(conf, auto_thresh, review_thresh)
        return Classification(
            block_id=block.id, role=SemanticRole.BODY_CONTENT,
            confidence=conf, reasons=reasons, automation=auto,
        )

    # -- detection helpers --

    def _identify_variable_blocks(self, blocks, cover_end_index: int) -> set[str]:
        """Quick heuristic: cover-region paragraphs matching label:value patterns."""
        from praktikit.utils.text import split_label_value

        ids: set[str] = []
        for b in blocks:
            if not isinstance(b, ParagraphBlock):
                continue
            if b.index >= cover_end_index:
                continue
            if split_label_value(b.text.strip()):
                ids.append(b.id)
        return set(ids)

    def _is_cover_static(self, text: str) -> bool:
        lower = text.lower().strip()
        return any(kw in lower for kw in _COVER_KEYWORDS)

    def _is_label_like(self, text: str) -> bool:
        """True when text looks like an identity label, with or without a value."""
        from praktikit.utils.text import normalize, split_label_value
        if not text:
            return False
        if split_label_value(text):
            return True
        label = normalize(text).lower().strip(" :")
        return label in {
            "nama", "nim", "npm", "nrp", "kelas", "kelompok", "program studi",
            "prodi", "jurusan", "mata kuliah", "modul", "nomor modul", "judul",
            "judul modul", "asisten", "dosen", "tanggal", "semester",
            "name", "student id", "student number", "class", "course", "module",
            "title", "assistant", "lecturer", "date",
        }

    def _find_references_heading(self, blocks) -> set[str]:
        ids: set[str] = []
        for b in blocks:
            if not isinstance(b, ParagraphBlock):
                continue
            if _REFERENCES_RE.match(b.text.strip()):
                ids.append(b.id)
        return set(ids)

    def _find_appendix_heading(self, blocks) -> set[str]:
        ids: set[str] = []
        for b in blocks:
            if not isinstance(b, ParagraphBlock):
                continue
            if _APPENDIX_RE.match(b.text.strip()):
                ids.append(b.id)
        return set(ids)

    def _find_cover_node(self, structure_tree: list[StructureNode]) -> StructureNode | None:
        for node in structure_tree:
            if node.node_type == "cover":
                return node
        return None
