"""Mutation engine (spec Section 23/41).

Applies a :class:`~praktikit.models.cleaning.CleaningPlan` to a **clone** of the
source DOCX. The principle is *Preserve by Mutation, Not Reconstruction*: we
edit XML in place, preserving all untouched structure/styles/relationships.

Key utilities preserve run-level formatting when replacing/clearing text.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from praktikit.models.cleaning import CleaningAction, CleaningOperation, CleaningPlan
from praktikit.utils.xml_namespaces import find, findall, qn

# Hardened XML parser for mutation output validation.
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)


class MutationEngine:
    """Applies a cleaning plan to a DOCX clone via raw OOXML mutation."""

    def __init__(self, source_path: Path):
        self.source_path = source_path
        self._working_path: Path | None = None

    def clone_to_working(self) -> Path:
        """Copy source to a temp working file; returns the working path."""
        if self._working_path is not None:
            return self._working_path
        tmp_dir = Path(tempfile.mkdtemp(prefix="praktikit_"))
        self._working_path = tmp_dir / f"working_{uuid.uuid4().hex}.docx"
        shutil.copy2(self.source_path, self._working_path)
        return self._working_path

    def apply(self, plan: CleaningPlan) -> Path:
        """Apply the plan to the cloned DOCX; returns the working file path."""
        working = self.clone_to_working()
        # Read word/document.xml, parse, mutate, write back.
        with ZipFile(working, "r") as zf:
            doc_bytes = zf.read("word/document.xml")

        root = etree.fromstring(doc_bytes, _PARSER)
        body = root.find(qn("w:body"))
        if body is None:
            return working  # no content to mutate

        # Build a block_id → element map by walking body in order.
        id_map = self._build_id_map(body)
        ops_by_target = plan.by_target()

        for target, ops in ops_by_target.items():
            element = id_map.get(target)
            if element is None:
                continue
            for op in ops:
                self._apply_op(element, op, root)

        # Write back the mutated document.xml.
        mutated_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        self._replace_part(working, "word/document.xml", mutated_bytes)

        return working

    def _build_id_map(self, body) -> dict[str, etree._Element]:
        """Walk body children and assign stable ids matching the parser."""
        counters = {"p": 0, "tbl": 0, "img": 0, "sec": 0}
        result: dict[str, etree._Element] = {}

        for child in body.iterchildren():
            tag_local = etree.QName(child.tag).localname
            if tag_local == "p":
                counters["p"] += 1
                bid = f"p-{counters['p']:06d}"
                result[bid] = child
                # Images within this paragraph get sequential ids.
                for drawing in findall(child, "w:r/w:drawing"):
                    counters["img"] += 1
                    img_id = f"img-{counters['img']:06d}"
                    result[img_id] = drawing
                # Mid-document section break.
                if find(child, "w:pPr/w:sectPr") is not None:
                    counters["sec"] += 1
                    result[f"sec-{counters['sec']:06d}"] = child
            elif tag_local == "tbl":
                counters["tbl"] += 1
                bid = f"tbl-{counters['tbl']:06d}"
                result[bid] = child
            elif tag_local == "sectPr":
                counters["sec"] += 1
                result[f"sec-{counters['sec']:06d}"] = child

        return result

    def _apply_op(self, element: etree._Element, op: CleaningOperation, root: etree._Element) -> None:
        action = op.action
        tag_local = etree.QName(element.tag).localname

        if action == CleaningAction.KEEP:
            return

        if action == CleaningAction.KEEP_IMAGE:
            return

        if action == CleaningAction.REMOVE:
            # Remove element entirely (e.g. content tables).
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)
            return

        if action == CleaningAction.REMOVE_CONTENT_IMAGE:
            # Remove the drawing element (inline or anchored).
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)
            return

        if action == CleaningAction.REPLACE_WITH_PLACEHOLDER:
            ph = op.placeholder or "[VARIABLE]"
            if tag_local == "p":
                self._replace_paragraph_text(element, ph)
            elif tag_local == "tbl" and op.cell:
                self._replace_table_cell(element, op.cell, ph)
            return

        if action == CleaningAction.KEEP_STRUCTURE_CLEAR_CONTENT:
            ph = op.placeholder or "[Isi di sini]"
            if tag_local == "p":
                self._replace_paragraph_text(element, ph)
            return

        if action == CleaningAction.CLEAR_TABLE_DATA:
            if tag_local == "tbl":
                self._clear_table_data(element)
            return

        if action == CleaningAction.KEEP_TABLE_STRUCTURE:
            # No mutation needed (handled by CLEAR_TABLE_DATA per cell if applicable).
            return

        # Unknown action: no-op (preserve).

    def _replace_paragraph_text(self, para: etree._Element, new_text: str) -> None:
        """Replace all text in a paragraph while preserving paragraph props and first run formatting."""
        # Find all runs and their rPr.
        runs = findall(para, "w:r")
        if not runs:
            # No runs: create one.
            new_run = etree.SubElement(para, qn("w:r"))
            t = etree.SubElement(new_run, qn("w:t"))
            t.text = new_text
            return

        # Keep the first run's rPr, remove all runs, create one new run.
        first_run = runs[0]
        rPr = find(first_run, "w:rPr")
        # Remove all existing runs.
        for run in runs:
            para.remove(run)
        # Create new run with preserved rPr.
        new_run = etree.SubElement(para, qn("w:r"))
        if rPr is not None:
            new_run.insert(0, etree.fromstring(etree.tostring(rPr)))
        t = etree.SubElement(new_run, qn("w:t"))
        # Preserve xml:space if the placeholder contains leading/trailing spaces.
        if new_text != new_text.strip():
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = new_text

    def _replace_table_cell(self, tbl: etree._Element, cell: tuple[int, int], new_text: str) -> None:
        """Replace text in a specific table cell (row, col)."""
        row_idx, col_idx = cell
        rows = findall(tbl, "w:tr")
        if row_idx >= len(rows):
            return
        tr = rows[row_idx]
        tcs = findall(tr, "w:tc")
        # Account for gridSpan when mapping col_idx.
        effective_col = 0
        for tc in tcs:
            grid_span_el = find(tc, "w:tcPr/w:gridSpan")
            span = 1
            if grid_span_el is not None:
                span = int(grid_span_el.get(qn("w:val"), "1") or "1")
            if effective_col <= col_idx < effective_col + span:
                # Found the cell.
                for p in findall(tc, "w:p"):
                    self._replace_paragraph_text(p, new_text)
                return
            effective_col += span

    def _clear_table_data(self, tbl: etree._Element) -> None:
        """Clear all cell text except the header row."""
        rows = findall(tbl, "w:tr")
        for row_idx, tr in enumerate(rows):
            if row_idx == 0:
                continue  # keep header
            for tc in findall(tr, "w:tc"):
                for p in findall(tc, "w:p"):
                    self._replace_paragraph_text(p, "")

    def _replace_part(self, docx_path: Path, part_name: str, data: bytes) -> None:
        """Replace a part inside the DOCX zip with new data."""
        tmp_path = docx_path.with_suffix(".tmp.docx")
        with ZipFile(docx_path, "r") as zin:
            with ZipFile(tmp_path, "w") as zout:
                for info in zin.infolist():
                    if info.filename == part_name:
                        zout.writestr(info, data)
                    else:
                        zout.writestr(info, zin.read(info.filename))
        tmp_path.replace(docx_path)
