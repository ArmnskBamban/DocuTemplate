# DocuTemplate Document Model Reference

> **Last Updated:** 2026-08-12  
> **Version:** 0.1.0  
> **Audience:** Developers extending or integrating with DocuTemplate

---

## Table of Contents

1. [Overview](#overview)
2. [Document Meta](#document-meta)
3. [Block Model](#block-model)
4. [Run Model](#run-model)
5. [Structure Model](#structure-model)
6. [Classification Model](#classification-model)
7. [Variables Model](#variables-model)
8. [Cleaning Model](#cleaning-model)
9. [Analysis Result](#analysis-result)
10. [ID Schemes](#id-schemes)
11. [Units and Conventions](#units-and-conventions)

---

## Overview

DocuTemplate's internal document model is built on **Pydantic v2** for validation, serialization, and type safety. The model captures:

- **Document-level metadata** (page layout, margins, sections, styles)
- **Ordered blocks** (paragraphs, tables, images, section boundaries)
- **Run-level formatting** (font, bold, italic, color)
- **Detected structure** (headings, hierarchy tree)
- **Semantic classifications** (roles, confidence, automation)
- **Identity variables** (fields to replace with placeholders)
- **Cleaning operations** (mutations to apply)

All models are **pure data** — no I/O, no side effects. They are designed for:

- **Serialization** (JSON for API, CLI output)
- **Validation** (reject invalid structures early)
- **Round-tripping** (parse → analyze → mutate → validate)

---

## Document Meta

**Location:** `models/document.py`

### DocumentMeta

Top-level document properties.

```python
class DocumentMeta(BaseModel):
    title: str | None = None
    core_creator: str | None = None
    page_layout: PageLayout = PageLayout()
    margins: Margins = Margins()
    section_count: int = 1
    sections: list[SectionMeta] = []
    styles: list[StyleInfo] = []
    numbering_definition_count: int = 0
    has_headers: bool = False
    has_footers: bool = False
    has_table_of_contents: bool = False
    toc_is_field: bool | None = None
```

**Key Fields:**
- `page_layout` — Primary section's page size and orientation
- `margins` — Primary section's margins (twips)
- `sections` — All section breaks in the document
- `styles` — Indexed styles from `styles.xml`
- `has_table_of_contents` — True if TOC detected (via `instrText` field)

### PageLayout

Physical page dimensions.

```python
class PageLayout(BaseModel):
    width_twips: int | None = None
    height_twips: int | None = None
    orientation: Orientation = Orientation.PORTRAIT
    size_name: str | None = None  # "A4", "Letter", etc.
```

**Units:** OOXML stores page dimensions in **twips** (1/1440 inch).

**Common sizes:**
- A4 Portrait: 11906 × 16838 twips
- Letter Portrait: 12240 × 15840 twips

### Margins

Page margins in twips.

```python
class Margins(BaseModel):
    top: int | None = None
    bottom: int | None = None
    left: int | None = None
    right: int | None = None
    gutter: int | None = None
    header: int | None = None  # Distance from top edge
    footer: int | None = None  # Distance from bottom edge
    
    def to_cm(self) -> dict[str, float | None]:
        """Convert to centimeters for display."""
```

**Conversion:** 1 cm = 567 twips

### SectionMeta

A document section (corresponds to `<w:sectPr>` in OOXML).

```python
class SectionMeta(BaseModel):
    id: str  # "sec-000001"
    index: int
    page_layout: PageLayout
    margins: Margins
    has_header: bool = False
    has_footer: bool = False
    different_first_page: bool = False
    header_rids: list[str] = []  # Relationship IDs
    footer_rids: list[str] = []
```

**Note:** Mid-document section breaks (e.g., landscape page in portrait document) are captured.

### StyleInfo

A summary of one style from `styles.xml`.

```python
class StyleInfo(BaseModel):
    style_id: str
    name: str
    style_type: str = "paragraph"  # paragraph | character | table
    based_on: str | None = None
    is_heading: bool = False
    heading_level: int | None = None  # 0 = Title, 1 = Heading 1, ...
    font_name: str | None = None
    font_size: float | None = None  # points
```

---

## Block Model

**Location:** `models/blocks.py`

### DocumentBlock (Union Type)

```python
DocumentBlock = ParagraphBlock | TableBlock | SectionBoundary
```

All blocks in `w:body` are represented as one of these three types, **in document order**.

### ParagraphBlock

A `<w:p>` element.

```python
class ParagraphBlock(BaseModel):
    id: str  # "p-000001"
    index: int  # Ordinal among ALL blocks
    block_type: BlockType = BlockType.PARAGRAPH
    text: str = ""
    runs: list[RunData] = []
    props: ParagraphProps = ParagraphProps()
    images: list[ImageInfo] = []
    style_fingerprint: tuple | None = None  # Assigned by style_analyzer
    
    @property
    def is_blank(self) -> bool:
        return not self.text.strip()
    
    @property
    def plain_format(self) -> RunFormat:
        """First run's format (fallback anchor)."""
```

**Key Fields:**
- `text` — Concatenated text of all runs
- `runs` — Run-level data (text + formatting)
- `props` — Paragraph properties (alignment, spacing, numbering, etc.)
- `images` — Images embedded in this paragraph
- `style_fingerprint` — Computed formatting signature for clustering

### ParagraphProps

Paragraph-level properties from `<w:pPr>`.

```python
class ParagraphProps(BaseModel):
    style_id: str | None = None
    style_name: str | None = None
    alignment: str | None = None  # "left" | "center" | "right" | "justify"
    outline_level: int | None = None  # 0 = top level
    left_indent: int | None = None  # twips
    right_indent: int | None = None
    first_line_indent: int | None = None
    space_before: int | None = None  # twips
    space_after: int | None = None
    line_spacing: float | None = None  # lines (1.0, 1.5, etc.)
    keep_with_next: bool = False
    keep_together: bool = False
    page_break_before: bool = False
    numbering: Numbering | None = None
    contains_page_break: bool = False
    contains_image: bool = False
    contains_field: bool = False
    has_section_properties: bool = False
```

### Numbering

Paragraph numbering reference (for lists/outlines).

```python
class Numbering(BaseModel):
    num_id: int | None = None
    ilvl: int | None = None  # Indentation level
    is_list: bool = False  # True when numbering is attached
```

### TableBlock

A `<w:tbl>` element, modeled as a 2D grid.

```python
class TableBlock(BaseModel):
    id: str  # "tbl-000001"
    index: int
    block_type: BlockType = BlockType.TABLE
    rows: int = 0
    columns: int = 0
    style_id: str | None = None
    style_name: str | None = None
    width_twips: int | None = None
    alignment: str | None = None
    grid: list[list[CellInfo]] = []  # grid[row][col]
    
    def flat_cells(self) -> list[CellInfo]:
        """All cells flattened."""
    
    def first_row_texts(self) -> list[str]:
        """Header row texts."""
```

### CellInfo

A table cell (`<w:tc>`).

```python
class CellInfo(BaseModel):
    row_index: int
    col_index: int
    text: str = ""
    grid_span: int = 1  # Horizontal merge
    v_merge: str | None = None  # "restart" | "continue"
    style_id: str | None = None
    
    @property
    def is_blank(self) -> bool:
        return not self.text.strip()
```

### ImageInfo

An image (`<w:drawing>`) inside a paragraph.

```python
class ImageInfo(BaseModel):
    id: str  # "img-000001"
    parent_paragraph_id: str  # Back-reference
    rel_id: str | None = None  # r:embed relationship ID
    target: str | None = None  # "word/media/image1.png"
    inline: bool = True
    width_emu: int | None = None  # EMUs (English Metric Units)
    height_emu: int | None = None
```

**Note:** 1 EMU = 1/914400 inch

### SectionBoundary

Marks a section break in document order.

```python
class SectionBoundary(BaseModel):
    id: str  # "sec-000001"
    index: int
    block_type: BlockType = BlockType.SECTION_BOUNDARY
    section: SectionMeta
```

---

## Run Model

**Location:** `models/runs.py`

### RunData

A run's text + formatting.

```python
class RunData(BaseModel):
    text: str = ""
    format: RunFormat = RunFormat()
    
    @property
    def is_bold(self) -> bool:
        return bool(self.format.bold)
```

### RunFormat

Character-level formatting from `<w:rPr>`.

```python
class RunFormat(BaseModel):
    font_name: str | None = None
    font_size: float | None = None  # Points
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    color: str | None = None  # Hex RGB, e.g., "FF0000"
    highlight: str | None = None
    all_caps: bool | None = None
    small_caps: bool | None = None
    vert_align: str | None = None  # "superscript" | "subscript"
    
    def to_fingerprint(self) -> tuple:
        """Hashable signature for clustering."""
```

**Tri-state semantics:** `None` means "inherit / not set" (allows faithful round-tripping).

---

## Structure Model

**Location:** `models/structure.py`

### HeadingInfo

A detected heading with evidence.

```python
class HeadingInfo(BaseModel):
    block_id: str  # "p-000042"
    level: int  # 0 = chapter, 1 = section, 2 = subsection
    title: str
    number: str | None = None  # "I", "1.1", "A."
    number_scheme: str | None = None
    confidence: float = 0.0
    reasons: list[str] = []  # ["heading_style:Heading 1", "bold"]
```

**Level convention:**
- 0 = Chapter / Major (BAB I, CHAPTER I)
- 1 = Section (1.1, A.)
- 2+ = Subsection (1.1.1, A.1)

### StructureNode

A node in the document tree (recursive).

```python
class StructureNode(BaseModel):
    id: str  # "node-0001"
    node_type: str  # "cover" | "chapter" | "section" | "subsection"
    title: str | None = None
    number: str | None = None
    level: int = 0
    block_id: str | None = None  # Heading block (None for cover root)
    children: list[StructureNode] = []
    
    def walk(self):
        """Yield self and all descendants (pre-order)."""
```

**Example tree:**
```
StructureNode(node_type="cover", title="Cover", children=[...])
StructureNode(node_type="chapter", title="BAB I PENDAHULUAN", level=0, children=[
    StructureNode(node_type="section", title="1.1 Latar Belakang", level=1),
    StructureNode(node_type="section", title="1.2 Tujuan", level=1),
])
```

---

## Classification Model

**Location:** `models/classification.py`

### SemanticRole (Enum)

```python
class SemanticRole(StrEnum):
    COVER_STATIC = "cover_static"
    COVER_VARIABLE = "cover_variable"
    TITLE = "title"
    CHAPTER_HEADING = "chapter_heading"
    SECTION_HEADING = "section_heading"
    SUBSECTION_HEADING = "subsection_heading"
    BODY_CONTENT = "body_content"
    TABLE_TEMPLATE = "table_template"
    TABLE_CONTENT = "table_content"
    TABLE_IDENTITY = "table_identity"
    CAPTION = "caption"
    IMAGE_LOGO = "image_logo"
    IMAGE_CONTENT = "image_content"
    REFERENCES_HEADING = "references_heading"
    APPENDIX_HEADING = "appendix_heading"
    PAGE_BREAK = "page_break"
    BLANK = "blank"
    UNKNOWN = "unknown"
```

### Automation (Enum)

```python
class Automation(StrEnum):
    AUTO = "auto"       # Confidence high → act automatically
    REVIEW = "review"   # Confidence medium → act but flag
    KEEP = "keep"       # Confidence low → require user decision
```

### Classification

The result of classifying one block.

```python
class Classification(BaseModel):
    block_id: str
    role: SemanticRole
    confidence: float = 0.0
    reasons: list[str] = []  # ["chapter_pattern", "bold", "large_font"]
    signals: dict[str, float] = {}  # Explainability (future)
    automation: Automation = Automation.KEEP
```

**Confidence mapping:**
```python
def automation_for_confidence(confidence, auto_threshold, review_threshold):
    if confidence >= auto_threshold:  # ≥ 0.90
        return Automation.AUTO
    if confidence >= review_threshold:  # ≥ 0.70
        return Automation.REVIEW
    return Automation.KEEP
```

---

## Variables Model

**Location:** `models/variables.py`

### VariableField

A detected identity field to replace with a placeholder.

```python
class VariableField(BaseModel):
    id: str  # "v-000001"
    block_id: str  # Paragraph or table block
    label: str  # "Nama", "NIM"
    original_value: str  # **PII — never log**
    placeholder: str  # "{{NAMA}}", "{{NIM}}"
    standard: bool  # True if matched known field
    location: str  # "inline" | "stacked" | "table"
    cell: tuple[int, int] | None = None  # (row, col) for table vars
    
    def safe_view(self) -> dict:
        """Redact original_value for logs."""
```

**Detection Patterns:**
1. **Inline:** `Nama : John Doe` → single paragraph
2. **Stacked:** `Nama` on one paragraph, `John Doe` on next
3. **Table:** Two-column table with labels and values

**Standard placeholders:**
- `Nama` → `{{NAMA}}`
- `NIM` / `NPM` / `NRP` → `{{NIM}}`
- `Kelas` → `{{KELAS}}`
- `Program Studi` → `{{PROGRAM_STUDI}}`
- Unknown fields → `{{FIELD_1}}`, `{{FIELD_2}}`, ...

---

## Cleaning Model

**Location:** `models/cleaning.py`

### CleaningAction (Enum)

```python
class CleaningAction(StrEnum):
    KEEP = "keep"
    CLEAR_TEXT = "clear_text"
    REMOVE = "remove"
    REPLACE_WITH_PLACEHOLDER = "replace_with_placeholder"
    KEEP_STRUCTURE_CLEAR_CONTENT = "keep_structure_clear_content"
    KEEP_TABLE_STRUCTURE = "keep_table_structure"
    CLEAR_TABLE_DATA = "clear_table_data"
    REMOVE_CONTENT_IMAGE = "remove_content_image"
    KEEP_IMAGE = "keep_image"
    REVIEW_REQUIRED = "review_required"
```

### CleaningOperation

One mutation to apply.

```python
class CleaningOperation(BaseModel):
    target: str  # Block ID: "p-000042", "tbl-000003", "img-000005"
    action: CleaningAction
    placeholder: str | None = None  # Replacement text
    variable_id: str | None = None  # "v-000001"
    cell: tuple[int, int] | None = None  # (row, col) for table ops
    confidence: float | None = None
    reason: str | None = None
```

**Examples:**
```python
# Replace identity field
CleaningOperation(
    target="p-000005",
    action=CleaningAction.REPLACE_WITH_PLACEHOLDER,
    placeholder="{{NAMA}}",
    variable_id="v-000001",
    confidence=0.90,
    reason="variable:Nama"
)

# Clear body content
CleaningOperation(
    target="p-000042",
    action=CleaningAction.KEEP_STRUCTURE_CLEAR_CONTENT,
    placeholder="[Isi hasil praktikum di sini]",
    confidence=0.92,
    reason="body_content"
)

# Remove content image
CleaningOperation(
    target="img-000003",
    action=CleaningAction.REMOVE_CONTENT_IMAGE,
    placeholder="[Masukkan gambar hasil praktikum di sini]",
    confidence=0.75,
    reason="body_image"
)
```

### CleaningPlan

The complete, reviewable mutation list.

```python
class CleaningPlan(BaseModel):
    operations: list[CleaningOperation] = []
    notes: list[str] = []
    warnings: list[str] = []  # Uncertain elements
    
    def by_target(self) -> dict[str, list[CleaningOperation]]:
        """Group operations by target block."""
    
    def action_counts(self) -> dict[str, int]:
        """Count operations by action type."""
```

---

## Analysis Result

**Location:** `models/analysis.py`

### AnalysisSummary

Headline counts for UI display.

```python
class AnalysisSummary(BaseModel):
    paragraphs: int = 0
    tables: int = 0
    images: int = 0
    sections: int = 0
    major_headings: int = 0
    subheadings: int = 0
    variables: int = 0
```

### AnalysisResult

The complete analysis output.

```python
class AnalysisResult(BaseModel):
    document_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    source_name: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    document_meta: DocumentMeta
    summary: AnalysisSummary
    blocks: list[DocumentBlock] = []
    structure: list[StructureNode] = []
    headings: list[HeadingInfo] = []
    classifications: dict[str, Classification] = {}  # {block_id: Classification}
    variables: list[VariableField] = []
    cleaning_plan: CleaningPlan | None = None
    warnings: list[str] = []
    uncertain_elements: list[str] = []  # Block IDs needing review
    
    def to_debug_dict(self) -> dict:
        """JSON-safe view with redacted PII."""
```

**Usage:**
```python
generator = TemplateGenerator()
analysis = generator.analyze("source.docx")

print(analysis.summary)
# AnalysisSummary(paragraphs=156, tables=3, images=2, ...)

for h in analysis.headings:
    print(f"L{h.level} {h.title} (conf={h.confidence:.2f})")

for v in analysis.variables:
    print(f"{v.label} → {v.placeholder}")
```

---

## ID Schemes

### Stable Positional IDs

All IDs are assigned during parsing based on element position in `w:body`:

| Type | Format | Example |
|------|--------|---------|
| Paragraph | `p-NNNNNN` | `p-000001`, `p-000042` |
| Table | `tbl-NNNNNN` | `tbl-000001` |
| Image | `img-NNNNNN` | `img-000003` |
| Section | `sec-NNNNNN` | `sec-000001` |
| Variable | `v-NNNNNN` | `v-000001` |
| Structure Node | `node-NNNN` | `node-0042` |

**Why 6 digits?** Supports documents up to 999,999 elements (sufficient for 10,000-page reports).

**Stability guarantee:** Because mutation operates on a byte-identical clone, re-walking assigns the same IDs.

### Document ID

Session/document ID: `uuid.uuid4().hex` (32-char lowercase hex)

**Example:** `a1b2c3d4e5f67890abcdef1234567890`

---

## Units and Conventions

### OOXML Units

| Unit | Description | Conversion |
|------|-------------|------------|
| **Twip** | 1/1440 inch, 1/20 point | 1 cm = 567 twips |
| **Point (pt)** | 1/72 inch | Font sizes |
| **EMU** | English Metric Unit, 1/914400 inch | Image dimensions |
| **Half-point** | 1/144 inch | Font sizes in OOXML XML (we convert to points) |

### Display Conversions

```python
# Twips to cm
def to_cm(twips: int) -> float:
    return twips / 567.0

# Points to cm
def pt_to_cm(pt: float) -> float:
    return pt * 2.54 / 72
```

### Tri-State Semantics

Pydantic models use **`None`** to mean "not set / inherit":

```python
bold: bool | None = None
# None = inherit from style
# True = explicitly bold
# False = explicitly not bold
```

This allows faithful round-tripping without collapsing unknowns to `False`.

---

## JSON Serialization

All models support JSON serialization via Pydantic:

```python
# To JSON
analysis_json = analysis.model_dump_json(indent=2)

# From JSON
analysis = AnalysisResult.model_validate_json(analysis_json)

# To dict (for API responses)
analysis_dict = analysis.model_dump(mode="json")
```

**Privacy note:** Use `to_debug_dict()` for debug dumps to redact PII.

---

## Example: Full Analysis Flow

```python
from praktikit.services.docx.template_generator import TemplateGenerator

generator = TemplateGenerator()
analysis = generator.analyze("Laporan_Praktikum.docx")

# Document meta
print(f"Page: {analysis.document_meta.page_layout.size_name}")
print(f"Sections: {analysis.document_meta.section_count}")

# Summary
print(f"Paragraphs: {analysis.summary.paragraphs}")
print(f"Major headings: {analysis.summary.major_headings}")

# Structure tree
for node in analysis.structure:
    print(f"{' ' * node.level * 2}{node.title}")

# Headings
for h in analysis.headings:
    conf_str = f"({h.confidence:.2f})"
    print(f"[L{h.level}] {h.title} {conf_str}")

# Variables
for v in analysis.variables:
    print(f"{v.label}: {v.original_value} → {v.placeholder}")

# Classifications
for block_id, clf in analysis.classifications.items():
    if clf.confidence < 0.70:  # Low confidence
        print(f"Uncertain: {block_id} → {clf.role} ({clf.confidence:.2f})")

# Cleaning plan
plan = analysis.cleaning_plan
print(f"Total operations: {len(plan.operations)}")
print(f"Action counts: {plan.action_counts()}")
```

---

## Extension Points

### Adding a New Block Type

1. Define new class in `models/blocks.py`:
   ```python
   class CustomBlock(BaseModel):
       id: str
       index: int
       block_type: BlockType = BlockType.CUSTOM
       # ... custom fields
   ```

2. Update union:
   ```python
   DocumentBlock = ParagraphBlock | TableBlock | SectionBoundary | CustomBlock
   ```

3. Update parser to detect and emit new block type

### Adding a New Semantic Role

1. Add to `SemanticRole` enum in `models/classification.py`
2. Add detection logic in `semantic_classifier.py`
3. Add action mapping in `cleaning_planner.py`
4. Add mutation logic in `mutation_engine.py` (if needed)

### Adding Custom Metadata

All models use `model_config = ConfigDict(extra="ignore")`, so extra fields are silently dropped. To add custom fields:

1. Subclass the model
2. Add fields
3. Use `model_config = ConfigDict(extra="allow")` if dynamic fields needed

---

## References

- [Architecture Document](./architecture.md)
- [Pydantic v2 Documentation](https://docs.pydantic.dev/)
- [OOXML Specification](http://officeopenxml.com/WPparagraph.php)
- [python-docx API](https://python-docx.readthedocs.io/)

---

**Questions?** See `handoff.md` for file-by-file reference and implementation details.
