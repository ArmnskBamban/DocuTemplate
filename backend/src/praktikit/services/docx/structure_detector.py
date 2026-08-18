"""Structure detection engine (spec Section 14).

Identifies headings, the cover region, and builds a chapter hierarchy using
structural signals (style/outline level), visual signals (bold/size/caps/alignment),
text signals (BAB/CHAPTER/numbering patterns), and statistical clustering
(fingerprints). **Never hardcoded to a specific report structure** (Section 56).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from praktikit.models.blocks import ParagraphBlock
from praktikit.models.document import StyleInfo
from praktikit.models.structure import HeadingInfo, StructureNode
from praktikit.services.docx.style_analyzer import (
    annotate_fingerprints,
    cluster_fingerprints,
    effective_outline_level,
)

if TYPE_CHECKING:
    from praktikit.models.blocks import DocumentBlock

# --- heading text patterns (spec Section 14) ---

# BAB / CHAPTER + optional roman/arabic number
_CHAPTER_RE = re.compile(
    r"^\s*(?:BAB|CHAPTER|CH|BAB\s+KE)\s+(?:[IVXLCDM]+|\d+|[\d.]+)?\s*$",
    re.IGNORECASE,
)
# Decimal numbering: "1.", "1.1", "1.1.1", "2.", "2.3.1"
_DECIMAL_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+(.+)$")
# Roman section numbering: "I.", "II.", "III.", etc.
_ROMAN_LETTER_RE = re.compile(r"^\s*([IVXLCDM]+)[\.\s]+(.+)$")
# Letter numbering: "A.", "B.", "C."
_LETTER_RE = re.compile(r"^\s*([A-Z])\.\s+(.+)$")
# Plain "1 Title" or "1.1 Title"
_PLAIN_NUM_RE = re.compile(r"^\s*(\d+\.?\d*)\s+(.+)$")

# Cover static keywords (Indonesian / generic academic)
_COVER_KEYWORDS = {
    "universitas", "fakultas", "program studi", "jurusan",
    "laporan", "praktikum", "laboratorium", "lab",
    "disusun oleh", "disusun oleh:", "oleh", "asisten",
}


@dataclass
class StructureDetection:
    heading_info: list[HeadingInfo] = field(default_factory=list)
    structure_tree: list[StructureNode] = field(default_factory=list)
    cover_end_index: int = 0  # index of first block after the cover region


class StructureDetector:
    """Detect document structure (headings, cover, hierarchy) from parsed blocks."""

    def __init__(
        self,
        blocks: list[DocumentBlock],
        styles_by_id: dict[str, StyleInfo],
    ):
        self.blocks = blocks
        self.paragraphs = [b for b in blocks if isinstance(b, ParagraphBlock)]
        self.styles = styles_by_id
        self.fingerprints = annotate_fingerprints(self.paragraphs)
        self.clusters = cluster_fingerprints(self.fingerprints)

    def detect(self) -> StructureDetection:
        all_headings = self._detect_headings()
        cover_end = self._detect_cover_end(all_headings)
        # Exclude headings in the cover region from the main list — they'll be
        # classified as COVER_STATIC / COVER_VARIABLE by the semantic classifier.
        content_headings = [h for h in all_headings if self._block_index(h.block_id) is not None and self._block_index(h.block_id) >= cover_end]
        tree = self._build_hierarchy(all_headings, cover_end)
        return StructureDetection(
            heading_info=content_headings, structure_tree=tree, cover_end_index=cover_end
        )

    # -- heading detection ----------------------------------------------------

    def _detect_headings(self) -> list[HeadingInfo]:
        result: list[HeadingInfo] = []
        for block in self.paragraphs:
            info = self._classify_heading(block)
            if info is not None:
                result.append(info)
        return result

    def _classify_heading(self, block: ParagraphBlock) -> HeadingInfo | None:
        """Compute heading confidence from all available signals."""
        text = block.text.strip()
        if not text:
            return None
        # Skip very long paragraphs — headings are typically short.
        if len(text) > 120:
            return None

        score = 0.0
        reasons: list[str] = []
        level: int | None = None
        number: str | None = None
        title = text

        # --- structural signal: Word heading style ---
        style_id = block.props.style_id
        style_name = block.props.style_name
        si = self.styles.get(style_id) if style_id else None

        if si and si.is_heading:
            level = si.heading_level if si.heading_level is not None else 0
            score += 0.40
            reasons.append(f"heading_style:{style_name}")

        # outline level (explicit or from style)
        ol = effective_outline_level(block.props, self.styles, style_id)
        if ol is not None and level is None:
            level = ol
            score += 0.35
            reasons.append("outline_level")

        # --- text signal: BAB / CHAPTER pattern ---
        m_chap = _CHAPTER_RE.match(text)
        if m_chap:
            level = 0
            score += 0.35
            reasons.append("chapter_pattern")
            num_part = text.strip().split(None, 1)[-1].strip().rstrip(".")
            number = num_part if num_part else None
            title = text.strip()
            return self._heading(block, level, title, number, score, reasons)

        # --- text signal: numbered heading (1.1, A., I., etc.) ---
        parsed_num = self._parse_numbering(text)
        if parsed_num is not None:
            num_str, num_title, detected_level = parsed_num
            # Reject long body-like numbered text (e.g. "1. Mengetahui cara kerja...")
            # unless backed by a heading style. Heading titles are typically short.
            has_style_support = si is not None and si.is_heading
            from praktikit.utils.text import word_count

            if not has_style_support and (
                word_count(num_title) > 7 or (detected_level == 0 and re.match(r"^\s*\d+\.\s+", text))
            ):
                parsed_num = None  # skip as heading/list item
            else:
                if level is None:
                    level = detected_level
                number = num_str
                title = num_title
                score += 0.30
                reasons.append(f"numbering:{num_str}")

        # --- visual signals: bold, uppercase, centered, font size ---
        fmt = block.plain_format
        if fmt.bold is True:
            score += 0.12
            reasons.append("bold")
        if fmt.font_size is not None and fmt.font_size >= 13:
            score += 0.10
            reasons.append("large_font")
        from praktikit.utils.text import uppercase_ratio

        uc = uppercase_ratio(text)
        if uc > 0.7 and len(text) > 2:
            score += 0.10
            reasons.append("uppercase")
        if block.props.alignment == "center" and len(text) < 60:
            score += 0.08
            reasons.append("centered")

        # --- statistical signal: fingerprint cluster ---
        fp = self.fingerprints.get(block.id)
        if fp is not None:
            cluster = self.clusters.get(fp, [])
            if len(cluster) >= 2:
                score += 0.08
                reasons.append(f"recurring_style(x{len(cluster)})")

        # Short text bonus (headings are usually short).
        if len(text.split()) <= 6:
            score += 0.05

        # Cap at 0.99 and require a minimum score.
        score = min(score, 0.99)
        if score < 0.25:
            return None

        return self._heading(block, level or 0, title, number, score, reasons)

    def _parse_numbering(self, text: str) -> tuple[str, str, int] | None:
        """Try to parse a numbered heading pattern. Returns (number, title, level)."""
        m = _DECIMAL_RE.match(text)
        if m:
            num_str = m.group(1)
            title = m.group(2).strip().rstrip(".")
            level = num_str.count(".")
            return num_str, title, level
        m = _ROMAN_LETTER_RE.match(text)
        if m:
            num_str = m.group(1)
            title = m.group(2).strip().rstrip(".")
            from praktikit.utils.text import is_roman_numeral

            if is_roman_numeral(num_str):
                level = 0
                return num_str, title, level
        m = _LETTER_RE.match(text)
        if m:
            num_str = m.group(1)
            title = m.group(2).strip().rstrip(".")
            return num_str, title, 2
        m = _PLAIN_NUM_RE.match(text)
        if m:
            num_str = m.group(1).rstrip(".")
            title = m.group(2).strip().rstrip(".")
            level = num_str.count(".") if "." in num_str else 0
            return num_str, title, level
        return None

    def _heading(
        self, block: ParagraphBlock, level: int, title: str, number: str | None, score: float, reasons: list[str]
    ) -> HeadingInfo:
        return HeadingInfo(
            block_id=block.id,
            level=level,
            title=title,
            number=number,
            confidence=score,
            reasons=reasons,
        )

    # -- cover detection -------------------------------------------------------

    def _detect_cover_end(self, headings: list[HeadingInfo]) -> int:
        """Identify where the cover ends: before the first major chapter heading (level 0 with 'BAB' pattern).

        If no such heading is found, return 0 (no cover region).
        """
        for h in headings:
            # A true chapter heading: level 0 AND title starts with 'BAB' (Indonesian) or 'CHAPTER'
            if h.level == 0 and (h.title.upper().startswith('BAB') or 'CHAPTER' in h.title.upper()):
                idx = self._block_index(h.block_id)
                if idx is not None:
                    # Cover ends before this chapter
                    return idx
        return 0

    # -- hierarchy ------------------------------------------------------------

    def _build_hierarchy(self, headings: list[HeadingInfo], cover_end: int) -> list[StructureNode]:
        """Build a tree of StructureNode from detected headings."""
        if not headings:
            return []

        # Separate cover headings (before first major heading) from content headings.
        cover_headings: list[HeadingInfo] = []
        content_headings: list[HeadingInfo] = []
        for h in headings:
            idx = self._block_index(h.block_id)
            if idx is not None and idx < cover_end:
                cover_headings.append(h)
            else:
                content_headings.append(h)

        nodes: list[StructureNode] = []
        node_id = 0
        stack: list[StructureNode] = []  # ancestor stack

        # Cover node.
        if cover_headings:
            cover_node = StructureNode(
                id=f"node-{node_id:04d}", node_type="cover", title="Cover", level=-1
            )
            node_id += 1
            for h in cover_headings:
                child = StructureNode(
                    id=f"node-{node_id:04d}",
                    node_type="section",
                    title=h.title,
                    number=h.number,
                    level=h.level,
                    block_id=h.block_id,
                )
                node_id += 1
                cover_node.children.append(child)
            nodes.append(cover_node)

        # Content nodes — nest based on level.
        for h in content_headings:
            node = StructureNode(
                id=f"node-{node_id:04d}",
                node_type="chapter" if h.level == 0 else "section" if h.level == 1 else "subsection",
                title=h.title,
                number=h.number,
                level=h.level,
                block_id=h.block_id,
            )
            node_id += 1
            # Pop stack to find correct parent (level < node.level).
            while stack and stack[-1].level >= node.level:
                stack.pop()
            if stack:
                stack[-1].children.append(node)
            else:
                nodes.append(node)
            stack.append(node)

        return nodes

    # -- helpers --------------------------------------------------------------

    def _block_index(self, block_id: str) -> int | None:
        for b in self.blocks:
            if b.id == block_id:
                return b.index
        return None
