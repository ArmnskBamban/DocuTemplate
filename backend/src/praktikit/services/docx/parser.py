"""Ordered DOCX parser (spec Section 12/13).

Walks ``word/document.xml``'s body **in element order**, emitting
:class:`DocumentBlock` items with stable positional ids. We use python-docx's
high-level API where it is well-supported (paragraph/run formatting, styles,
relationships) and drop to raw lxml for the parts it doesn't expose
(numbering refs, outline level, drawings, section properties).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from docx.document import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from praktikit.models.blocks import (
    BlockType,
    CellInfo,
    DocumentBlock,
    ImageInfo,
    Numbering,
    ParagraphBlock,
    ParagraphProps,
    SectionBoundary,
    TableBlock,
)
from praktikit.models.document import (
    DocumentMeta,
    Margins,
    Orientation,
    PageLayout,
    SectionMeta,
    StyleInfo,
)
from praktikit.models.runs import RunData, RunFormat
from praktikit.utils.xml_namespaces import find, findall, qn

# Standard paper sizes (width x height in twips) for best-effort naming.
_PAPER_SIZES = {
    (11906, 16838): "A4",
    (12240, 15840): "Letter",
    (12240, 20160): "Legal",
    (16838, 11906): "A4",  # landscape swapped
    (15840, 12240): "Letter",
}


@dataclass
class ParseOutput:
    document_meta: DocumentMeta
    blocks: list[DocumentBlock]
    styles_by_id: dict[str, StyleInfo]


class DocxParser:
    """Parses a validated DOCX into an ordered block model + document metadata."""

    def __init__(self, document: Document, source_name: str = ""):
        self.document = document
        self.source_name = source_name
        self._body = document.element.body
        self._rels = document.part.rels
        self._style_index = _index_styles(document)

    # -- public API -----------------------------------------------------------

    @classmethod
    def from_path(cls, path: str | os.PathLike) -> DocxParser:
        from docx import Document as _OpenDocument  # local import keeps module import cheap

        p = Path(path)
        doc = _OpenDocument(str(p))
        return cls(doc, source_name=p.name)

    def parse(self) -> ParseOutput:
        blocks = self._parse_blocks()
        sections = self._collect_sections()
        meta = self._build_document_meta(sections)
        return ParseOutput(document_meta=meta, blocks=blocks, styles_by_id=self._style_index)

    # -- ordered block walk ---------------------------------------------------

    def _parse_blocks(self) -> list[DocumentBlock]:
        blocks: list[DocumentBlock] = []
        counters = {"p": 0, "tbl": 0, "img": 0, "sec": 0}
        index = 0

        def next_id(kind: str) -> str:
            counters[kind] += 1
            return f"{kind}-{counters[kind]:06d}"

        for child in self._body.iterchildren():
            if isinstance(child, CT_P):
                para = Paragraph(child, self.document)
                pblock = self._parse_paragraph(para, next_id, index)
                blocks.append(pblock)
                index += 1
                # A mid-document section break lives inside the paragraph's pPr.
                sect_pr = find(child, "w:pPr/w:sectPr")
                if sect_pr is not None:
                    counters["sec"] += 1
                    sec = self._parse_section(sect_pr, f"sec-{counters['sec']:06d}", counters["sec"] - 1)
                    blocks.append(SectionBoundary(id=f"sec-{counters['sec']:06d}", index=index, section=sec))
                    index += 1
            elif isinstance(child, CT_Tbl):
                tbl = Table(child, self.document)
                blocks.append(self._parse_table(tbl, next_id, index))
                index += 1
            else:
                # Body-level (final) section properties or other top-level elements.
                if find(child, "w:sectPr") is not None and child.tag == qn("w:sectPr"):
                    counters["sec"] += 1
                    sec = self._parse_section(child, f"sec-{counters['sec']:06d}", counters["sec"] - 1)
                    blocks.append(SectionBoundary(id=f"sec-{counters['sec']:06d}", index=index, section=sec))
                    index += 1
                # else: ignore unknown top-level (e.g. w:bookmarkStart at body level is unusual)
        return blocks

    # -- paragraph ------------------------------------------------------------

    def _parse_paragraph(self, para: Paragraph, next_id, index: int) -> ParagraphBlock:
        pid = next_id("p")
        runs = [self._parse_run(r) for r in para.runs]
        text = para.text or "".join(r.text for r in runs)
        props = self._parse_paragraph_props(para)
        images = self._parse_images(para, pid, next_id)
        if images:
            props.contains_image = True
        return ParagraphBlock(
            id=pid,
            index=index,
            block_type=BlockType.PARAGRAPH,
            text=text,
            runs=runs,
            props=props,
            images=images,
        )

    def _parse_run(self, run) -> RunData:
        font = run.font
        size = None
        if font.size is not None:
            try:
                size = float(font.size.pt)
            except (AttributeError, ValueError):
                size = None
        color = None
        try:
            if font.color is not None and font.color.rgb is not None:
                color = str(font.color.rgb)
        except Exception:  # color access can raise for theme colors
            color = None
        vert = None
        if run.font.superscript:
            vert = "superscript"
        elif run.font.subscript:
            vert = "subscript"
        highlight = None
        if run.font.highlight_color is not None:
            highlight = str(run.font.highlight_color)
        fmt = RunFormat(
            font_name=font.name,
            font_size=size,
            bold=run.bold,
            italic=run.italic,
            underline=run.underline if isinstance(run.underline, bool) else (True if run.underline else None),
            color=color,
            highlight=highlight,
            all_caps=font.all_caps,
            small_caps=font.small_caps,
            vert_align=vert,
        )
        return RunData(text=run.text or "", format=fmt)

    def _parse_paragraph_props(self, para: Paragraph) -> ParagraphProps:
        pf = para.paragraph_format
        ct_p = para._p  # underlying lxml element
        style_id = None
        style_name = None
        if para.style is not None:
            try:
                style_id = para.style.style_id
            except Exception:
                style_id = None
            style_name = para.style.name
        # Outline level (not exposed by high-level API).
        outline = _attr_int(ct_p, "w:pPr/w:outlineLvl", "w:val")
        numbering = _parse_numbering(ct_p)
        has_page_break = _paragraph_has_page_break(ct_p)
        has_field = _paragraph_has_field(ct_p)
        has_sect = find(ct_p, "w:pPr/w:sectPr") is not None

        return ParagraphProps(
            style_id=style_id,
            style_name=style_name,
            alignment=_alignment_name(para.alignment),
            outline_level=outline,
            left_indent=_twips(pf.left_indent),
            right_indent=_twips(pf.right_indent),
            first_line_indent=_twips(pf.first_line_indent),
            space_before=_twips(pf.space_before),
            space_after=_twips(pf.space_after),
            line_spacing=_line_spacing_ratio(pf),
            keep_with_next=bool(pf.keep_with_next),
            keep_together=bool(pf.keep_together),
            page_break_before=bool(pf.page_break_before),
            numbering=numbering,
            contains_page_break=has_page_break,
            contains_field=has_field,
            has_section_properties=has_sect,
        )

    def _parse_images(self, para: Paragraph, pid: str, next_id) -> list[ImageInfo]:
        infos: list[ImageInfo] = []
        ct_p = para._p
        # w:drawing may be inline (wp:inline) or anchored (wp:anchor).
        for drawing in findall(ct_p, "w:r/w:drawing"):
            inline = find(drawing, "wp:inline") is not None
            rid = None
            blip = find(drawing, "wp:inline/a:graphic/a:graphicData/pic:pic/pic:blipFill/a:blip")
            if blip is None:
                blip = find(drawing, "wp:anchor/a:graphic/a:graphicData/pic:pic/pic:blipFill/a:blip")
            if blip is not None:
                rid = blip.get(qn("r:embed")) or blip.get(qn("r:link"))
            extent = find(drawing, "wp:inline/wp:extent")
            if extent is None:
                extent = find(drawing, "wp:anchor/wp:extent")
            width_emu = _to_int(extent.get("cx")) if extent is not None else None
            height_emu = _to_int(extent.get("cy")) if extent is not None else None
            target = None
            if rid and rid in self._rels:
                rel = self._rels[rid]
                if not rel.is_external:
                    target = rel.target_ref
            infos.append(
                ImageInfo(
                    id=next_id("img"),
                    parent_paragraph_id=pid,
                    rel_id=rid,
                    target=target,
                    inline=inline,
                    width_emu=width_emu,
                    height_emu=height_emu,
                )
            )
        return infos

    # -- table ----------------------------------------------------------------

    def _parse_table(self, table: Table, next_id, index: int) -> TableBlock:
        tid = next_id("tbl")
        ct_tbl = table._tbl
        style_id = _attr(ct_tbl, "w:tblPr/w:tblStyle", "w:val")
        style_name = self._style_index.get(style_id).name if style_id in self._style_index else style_id
        width = _attr_int(ct_tbl, "w:tblPr/w:tblW", "w:w")
        alignment = _attr(ct_tbl, "w:tblPr/w:jc", "w:val")

        grid: list[list[CellInfo]] = []
        rows = table.rows
        for row_idx, row in enumerate(rows):
            row_cells: list[CellInfo] = []
            # Use raw tc elements to read gridSpan/vMerge faithfully.
            tr = row._tr
            col_idx = 0
            for tc in findall(tr, "w:tc"):
                grid_span = _attr_int(tc, "w:tcPr/w:gridSpan", "w:val") or 1
                v_merge_el = find(tc, "w:tcPr/w:vMerge")
                v_merge = None
                if v_merge_el is not None:
                    vval = v_merge_el.get(qn("w:val"))
                    v_merge = "restart" if (vval and vval.lower() != "0") else "continue"
                cell_style = _attr(tc, "w:tcPr/w:tcStyle", "w:val")
                cell_text = _tc_text(tc)
                row_cells.append(
                    CellInfo(
                        row_index=row_idx,
                        col_index=col_idx,
                        text=cell_text,
                        grid_span=grid_span,
                        v_merge=v_merge,
                        style_id=cell_style,
                    )
                )
                col_idx += grid_span
            grid.append(row_cells)

        return TableBlock(
            id=tid,
            index=index,
            block_type=BlockType.TABLE,
            rows=len(rows),
            columns=max((len(r) for r in grid), default=0),
            style_id=style_id,
            style_name=style_name,
            width_twips=width,
            alignment=alignment,
            grid=grid,
        )

    # -- sections & document meta --------------------------------------------

    def _collect_sections(self) -> list[SectionMeta]:
        sections: list[SectionMeta] = []
        # python-docx exposes all sections (including those defined mid-document).
        for idx, section in enumerate(self.document.sections):
            sections.append(self._section_from_python_docx(section, idx))
        return sections

    def _section_from_python_docx(self, section, idx: int) -> SectionMeta:
        page_w = _twips_of_length(section.page_width)
        page_h = _twips_of_length(section.page_height)
        orientation = Orientation.LANDSCAPE if section.orientation == 1 else Orientation.PORTRAIT
        size_name = _PAPER_SIZES.get((page_w or 0, page_h or 0)) if (page_w and page_h) else None
        layout = PageLayout(
            width_twips=page_w,
            height_twips=page_h,
            orientation=orientation,
            size_name=size_name,
        )
        margins = Margins(
            top=_twips_of_length(section.top_margin),
            bottom=_twips_of_length(section.bottom_margin),
            left=_twips_of_length(section.left_margin),
            right=_twips_of_length(section.right_margin),
            gutter=_twips_of_length(section.gutter),
            header=_twips_of_length(section.header_distance),
            footer=_twips_of_length(section.footer_distance),
        )
        # Header/footer presence via the underlying sectPr relationship ids.
        sect_pr = section._sectPr
        header_rids = [str(r.get(qn("r:id"))) for r in findall(sect_pr, "w:headerReference")]
        footer_rids = [str(r.get(qn("r:id"))) for r in findall(sect_pr, "w:footerReference")]
        title_pg = find(sect_pr, "w:titlePg") is not None
        return SectionMeta(
            id=f"sec-{idx:06d}",
            index=idx,
            page_layout=layout,
            margins=margins,
            has_header=bool(header_rids),
            has_footer=bool(footer_rids),
            has_first_page_header_footer=title_pg,
            different_first_page=title_pg,
            header_rids=header_rids,
            footer_rids=footer_rids,
        )

    def _parse_section(self, sect_pr, sec_id: str, idx: int) -> SectionMeta:
        """Parse a raw ``<w:sectPr>`` element (mid-document or body-level)."""
        pg_sz = find(sect_pr, "w:pgSz")
        page_w = _to_int(pg_sz.get("w:w")) if pg_sz is not None else None
        page_h = _to_int(pg_sz.get("w:h")) if pg_sz is not None else None
        orient_attr = pg_sz.get(qn("w:orient")) if pg_sz is not None else None
        orientation = Orientation.LANDSCAPE if orient_attr == "landscape" else Orientation.PORTRAIT
        size_name = _PAPER_SIZES.get((page_w or 0, page_h or 0)) if (page_w and page_h) else None
        pg_mar = find(sect_pr, "w:pgMar")
        margins = Margins()
        if pg_mar is not None:
            margins = Margins(
                top=_to_int(pg_mar.get(qn("w:top"))),
                bottom=_to_int(pg_mar.get(qn("w:bottom"))),
                left=_to_int(pg_mar.get(qn("w:left"))),
                right=_to_int(pg_mar.get(qn("w:right"))),
                gutter=_to_int(pg_mar.get(qn("w:gutter"))),
                header=_to_int(pg_mar.get(qn("w:header"))),
                footer=_to_int(pg_mar.get(qn("w:footer"))),
            )
        header_rids = [str(r.get(qn("r:id"))) for r in findall(sect_pr, "w:headerReference")]
        footer_rids = [str(r.get(qn("r:id"))) for r in findall(sect_pr, "w:footerReference")]
        title_pg = find(sect_pr, "w:titlePg") is not None
        return SectionMeta(
            id=sec_id,
            index=idx,
            page_layout=PageLayout(
                width_twips=page_w,
                height_twips=page_h,
                orientation=orientation,
                size_name=size_name,
            ),
            margins=margins,
            has_header=bool(header_rids),
            has_footer=bool(footer_rids),
            has_first_page_header_footer=title_pg,
            different_first_page=title_pg,
            header_rids=header_rids,
            footer_rids=footer_rids,
        )

    def _build_document_meta(self, sections: list[SectionMeta]) -> DocumentMeta:
        primary = sections[0] if sections else SectionMeta(id="sec-000000", index=0)
        # Core properties (title/creator) — never logged.
        title = None
        creator = None
        try:
            cp = self.document.core_properties
            title = cp.title or None
            creator = cp.author or None
        except Exception:
            pass
        numbering_count = self._count_numbering_definitions()
        has_toc, toc_is_field = _detect_toc(self._body)
        return DocumentMeta(
            title=title,
            core_creator=creator,
            page_layout=primary.page_layout,
            margins=primary.margins,
            section_count=len(sections),
            sections=sections,
            styles=list(self._style_index.values()),
            numbering_definition_count=numbering_count,
            has_headers=any(s.has_header for s in sections),
            has_footers=any(s.has_footer for s in sections),
            has_table_of_contents=has_toc,
            toc_is_field=toc_is_field,
        )

    def _count_numbering_definitions(self) -> int:
        try:
            part = self.document.part.numbering_part
            if part is None:
                return 0
            root = part.element
            return len(findall(root, "w:num"))
        except Exception:
            return 0


# -- module-level helpers ----------------------------------------------------


def _index_styles(document: Document) -> dict[str, StyleInfo]:
    """Build a {style_id: StyleInfo} index from the document's styles."""
    from docx.enum.style import WD_STYLE_TYPE

    out: dict[str, StyleInfo] = {}
    try:
        styles = document.styles
    except Exception:
        return out
    for style in styles:
        try:
            sid = style.style_id
            name = style.name
        except Exception:
            continue
        type_name = "paragraph"
        try:
            if style.type == WD_STYLE_TYPE.CHARACTER:
                type_name = "character"
            elif style.type == WD_STYLE_TYPE.TABLE:
                type_name = "table"
        except Exception:
            type_name = "paragraph"
        is_heading = False
        heading_level = None
        try:
            nm = (name or "").lower()
            if nm.startswith("heading"):
                is_heading = True
                parts = nm.replace("heading", "").strip()
                heading_level = int(parts) if parts.isdigit() else 1
            elif nm.startswith("title"):
                is_heading = True
                heading_level = 0
        except Exception:
            pass
        font_name = None
        font_size = None
        try:
            if getattr(style, "font", None) is not None:
                font_name = style.font.name
                if style.font.size is not None:
                    font_size = float(style.font.size.pt)
        except Exception:
            pass
        based_on = None
        try:
            based_on = style.base_style.name if style.base_style else None
        except Exception:
            based_on = None
        out[sid] = StyleInfo(
            style_id=sid,
            name=name,
            style_type=type_name,
            based_on=based_on,
            is_heading=is_heading,
            heading_level=heading_level,
            font_name=font_name,
            font_size=font_size,
        )
    return out


def _alignment_name(alignment) -> str | None:
    if alignment is None:
        return None
    mapping = {
        WD_ALIGN_PARAGRAPH.LEFT: "left",
        WD_ALIGN_PARAGRAPH.CENTER: "center",
        WD_ALIGN_PARAGRAPH.RIGHT: "right",
        WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
    }
    return mapping.get(alignment, str(alignment).split()[-1].lower() if alignment else None)


def _twips(length) -> int | None:
    """Convert a python-docx Length to twips, or None."""
    if length is None:
        return None
    try:
        return int(length.twips)
    except Exception:
        return None


def _twips_of_length(length) -> int | None:
    return _twips(length)


def _to_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _attr(parent, path: str, attr: str) -> str | None:
    el = find(parent, path)
    if el is None:
        return None
    return el.get(qn(attr))


def _attr_int(parent, path: str, attr: str) -> int | None:
    return _to_int(_attr(parent, path, attr))


def _line_spacing_ratio(pf) -> float | None:
    """Line spacing as a multiple (1.0, 1.5, …) or None when fixed/unknown."""
    try:
        ls = pf.line_spacing
    except Exception:
        return None
    if ls is None:
        return None
    if isinstance(ls, (int, float)):
        return float(ls)
    # Length → exact spacing; represent as None ratio (we preserve it via mutation anyway).
    return None


def _parse_numbering(ct_p) -> Numbering | None:
    num_id = _attr_int(ct_p, "w:pPr/w:numPr/w:numId", "w:val")
    ilvl = _attr_int(ct_p, "w:pPr/w:numPr/w:ilvl", "w:val")
    if num_id is None and ilvl is None:
        return None
    return Numbering(num_id=num_id, ilvl=ilvl, is_list=num_id is not None)


def _paragraph_has_page_break(ct_p) -> bool:
    if find(ct_p, "w:pPr/w:pageBreakBefore") is not None:
        return True
    for br in findall(ct_p, "w:r/w:br"):
        if br.get(qn("w:type")) == "page":
            return True
    return find(ct_p, "w:r/w:lastRenderedPageBreak") is not None


def _paragraph_has_field(ct_p) -> bool:
    if find(ct_p, "w:fldSimple") is not None:
        return True
    return find(ct_p, "w:r/w:fldChar") is not None or find(ct_p, "w:r/w:instrText") is not None


def _tc_text(tc) -> str:
    """Concatenate all paragraph text within a table cell."""
    texts = []
    for p in findall(tc, "w:p"):
        buf = []
        for t in findall(p, "w:r/w:t"):
            if t.text:
                buf.append(t.text)
        texts.append("".join(buf))
    return "\n".join(t for t in texts if t != "")


def _detect_toc(body) -> tuple[bool, bool | None]:
    """Detect an automatic TOC field (instrText 'TOC') vs manual text."""
    for instr in findall(body, ".//w:instrText"):
        if instr.text and "TOC" in instr.text.upper():
            return True, True
    return False, None
