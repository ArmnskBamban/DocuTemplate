"""Style fingerprinting (spec Section 57).

Computes a per-paragraph formatting fingerprint used by the structure detector
to **cluster** paragraphs that share similar formatting — essential for
identifying headings in documents that use manual formatting instead of Word
Heading styles.
"""

from __future__ import annotations

from praktikit.models.blocks import ParagraphBlock, ParagraphProps


def paragraph_fingerprint(block: ParagraphBlock) -> tuple:
    """Return a hashable, comparable formatting profile for a paragraph.

    Captures the dominant visual properties (font size, bold, uppercase, etc.)
    that a human would use to visually distinguish heading levels. The first
    run's format is the primary anchor; bold/italic ratios across all runs add
    a secondary signal.
    """
    props = block.props
    fmt = block.plain_format  # first run's format

    # Bold / italic ratio across all runs (0.0–1.0).
    total = max(len(block.runs), 1)
    bold_count = sum(1 for r in block.runs if r.format.bold is True)
    italic_count = sum(1 for r in block.runs if r.format.italic is True)
    caps_count = sum(
        1 for r in block.runs if r.format.all_caps is True or r.format.small_caps is True
    )

    text = block.text
    from praktikit.utils.text import uppercase_ratio

    return (
        round(fmt.font_size, 1) if fmt.font_size is not None else None,
        bool(fmt.bold),
        round(bold_count / total, 2),
        round(italic_count / total, 2),
        round(caps_count / total, 2),
        uppercase_ratio(text),
        props.alignment,
        props.style_id,
        props.style_name,
        round(props.space_before or 0, -1) if props.space_before else None,
        round(props.space_after or 0, -1) if props.space_after else None,
    )


def annotate_fingerprints(blocks: list) -> dict[str, tuple]:
    """Compute and cache fingerprints for all paragraph blocks; return id→fingerprint."""
    from praktikit.models.blocks import ParagraphBlock

    fps: dict[str, tuple] = {}
    for b in blocks:
        if isinstance(b, ParagraphBlock):
            fps[b.id] = paragraph_fingerprint(b)
    return fps


def cluster_fingerprints(
    fingerprints: dict[str, tuple], min_cluster_size: int = 2
) -> dict[tuple, list[str]]:
    """Group paragraph ids by identical fingerprint.

    Returns ``{fingerprint: [block_id, ...]}``. Clusters smaller than
    ``min_cluster_size`` are still returned (singletons may be relevant for
    short documents).
    """
    clusters: dict[tuple, list[str]] = {}
    for pid, fp in fingerprints.items():
        clusters.setdefault(fp, []).append(pid)
    return clusters


def style_is_heading_style(style_name: str | None) -> bool:
    """True when ``style_name`` looks like a Word heading style."""
    if not style_name:
        return False
    name_lower = style_name.lower()
    return (
        name_lower.startswith("heading")
        or name_lower.startswith("title")
        or name_lower.startswith("toc ")
        or name_lower.startswith("subjudul")
    )


def effective_outline_level(
    block_props: ParagraphProps, styles_by_id: dict, style_id: str | None
) -> int | None:
    """Resolve the effective outline level: explicit pPr first, then style-based."""
    if block_props.outline_level is not None:
        return int(block_props.outline_level)
    if style_id and style_id in styles_by_id:
        si = styles_by_id[style_id]
        if si.is_heading and si.heading_level is not None:
            return si.heading_level
    return None
