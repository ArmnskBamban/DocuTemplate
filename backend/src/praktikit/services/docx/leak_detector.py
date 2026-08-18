"""Content leak detector (spec Section 42).

Second-pass scan: after generation, compare the source document's body content
against the generated output to catch old report content that was accidentally
left in the template. Uses word-shingle similarity — no LLM, no full-text
comparison needed, and nothing personal is logged.
"""

from __future__ import annotations

from pathlib import Path

from praktikit.models.analysis import AnalysisResult
from praktikit.models.blocks import ParagraphBlock, TableBlock
from praktikit.services.docx.parser import DocxParser
from praktikit.utils.text import normalize, shingles


def _block_text(block: object) -> str:
    """Extract comparable text from any block type.

    Paragraphs expose ``text`` directly; tables contribute the flattened cell
    texts so leak detection can compare table content too. Section boundaries
    and other block types contribute nothing.
    """
    if isinstance(block, ParagraphBlock):
        return block.text or ""
    if isinstance(block, TableBlock):
        return " ".join(cell.text or "" for cell in block.flat_cells())
    return ""


class LeakDetector:
    """Detect shared long text sequences between source body and output."""

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold

    def detect(self, source: Path, output: Path, analysis: AnalysisResult) -> list[str]:
        """Return a list of leaked text fragments found in the output.

        Compares BODY_CONTENT-classified source paragraphs against the output's
        body paragraphs. Headings, labels, and KEEP-classified content are
        excluded from the comparison.
        """
        # Collect source "cleanable" content: paragraphs classified as body content.
        source_cleanable = self._source_cleanable_paragraphs(analysis)

        output_paragraphs = self._output_paragraphs(output)

        leaks: list[str] = []
        for source_text in source_cleanable:
            source_shingles = shingles(source_text)
            if not source_shingles:
                continue
            for out_text in output_paragraphs:
                out_shingles = shingles(out_text)
                if not out_shingles:
                    continue
                overlap = len(source_shingles & out_shingles)
                if overlap / len(source_shingles) >= self.threshold:
                    leaks.append(normalize(source_text)[:120])
                    break
        return leaks

    def _source_cleanable_paragraphs(self, analysis: AnalysisResult) -> list[str]:
        """Paragraph/table texts from the source that were marked for cleaning."""
        texts: list[str] = []
        for block in analysis.blocks:
            clf = analysis.classifications.get(block.id)
            if clf is None:
                continue
            role = clf.role.value
            if role in ("body_content", "table_content"):
                texts.append(_block_text(block))
        return texts

    def _output_paragraphs(self, output: Path) -> list[str]:
        """All comparable paragraph/table texts in the generated output."""
        parse = DocxParser.from_path(output).parse()
        return [_block_text(b) for b in parse.blocks if _block_text(b)]

    def has_leaks(self, source: Path, output: Path, analysis: AnalysisResult) -> bool:
        return bool(self.detect(source, output, analysis))
