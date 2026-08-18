# DocuTemplate — Core Engine + CLI Implementation Plan

## Scope (this plan)
Deliver the **Section 91 milestone**: a deterministic, no-LLM DOCX engine that works end-to-end via CLI — `sample.docx → analyze → clean → clean-template.docx` — with a full test suite. **No REST API, no frontend** (explicitly deferred by the spec until the CLI works). The package/CLI name is `praktikit` (easily renameable later). Tooling: **uv + pyproject.toml**.

The governing principles from the spec drive every decision:
- **Preserve by Mutation, Not Reconstruction** (clone source → mutate XML → output; never rebuild a DOCX from scratch).
- **Ordered block model** with **stable positional IDs** (`p-000001`, `tbl-000001`, `img-000001`).
- **Formatting fidelity > aggressive cleanup**; **deterministic > AI**; **real functionality > mockups**.
- **Original file is immutable**; all work happens on a clone.
- **Unknown elements are preserved + flagged**, never deleted.

---

## 1. Repository structure (greenfield)

```
D:\Zcode\project7\
├── README.md
├── .gitignore
├── .env.example
├── docs/
│   ├── architecture.md
│   └── document-model.md
└── backend/
    ├── pyproject.toml                # uv project, package = praktikit (src layout)
    ├── src/praktikit/
    │   ├── __init__.py
    │   ├── __main__.py               # python -m praktikit
    │   ├── cli.py                    # click entry: analyze / clean
    │   ├── core/
    │   │   ├── config.py             # pydantic-settings (thresholds, limits, paths)
    │   │   ├── exceptions.py         # DocxValidationError, ParseError, GenerationError…
    │   │   └── logging.py            # structured logging, NO PII / body text
    │   ├── models/                   # Pydantic v2 schemas (serialization-free internal model)
    │   │   ├── document.py           # DocumentMeta, PageLayout, Margins, SectionMeta
    │   │   ├── blocks.py             # DocumentBlock + Paragraph/Table/Image/SectionBoundary
    │   │   ├── runs.py               # RunFormat
    │   │   ├── structure.py          # StructureNode tree, HeadingInfo
    │   │   ├── classification.py     # SemanticRole enum, Classification(confidence,reasons)
    │   │   ├── variables.py          # DetectedVariable
    │   │   ├── cleaning.py           # CleaningAction enum, CleaningOperation, CleaningPlan
    │   │   └── analysis.py           # AnalysisResult + AnalysisSummary
    │   ├── services/docx/
    │   │   ├── package_reader.py     # open + validate DOCX zip, secure OOXML part access
    │   │   ├── parser.py             # ordered block iterator over document.xml body
    │   │   ├── style_analyzer.py     # styles.xml + per-paragraph style fingerprint
    │   │   ├── structure_detector.py # headings, cover, chapters, hierarchy, clustering
    │   │   ├── semantic_classifier.py# Protocol + HeuristicSemanticClassifier (LLM = stub iface)
    │   │   ├── variable_detector.py  # identity label/value (inline, stacked, table)
    │   │   ├── placeholder.py        # contextual placeholder map (no LLM)
    │   │   ├── cleaning_planner.py   # analysis → CleaningPlan (+ confidence gating)
    │   │   ├── mutation_engine.py    # apply ops, preserve run/para formatting (raw OOXML)
    │   │   ├── template_generator.py # orchestrate clone→plan→mutate→validate→leak
    │   │   ├── validator.py          # input + output validation
    │   │   └── leak_detector.py      # second-pass old-content leak scan
    │   └── utils/
    │       ├── xml_namespaces.py     # qn() helper + ns map
    │       └── text.py               # normalization, label-value regexes
    └── tests/
        ├── conftest.py
        ├── fixtures/builders.py      # programmatic DOCX builders for Fixture 1–5
        ├── unit/…                    # parser, detector, classifier, vars, planner, mutation, leak
        └── integration/…             # end-to-end, golden, leak regression
```

Frontend (`frontend/`) and `app/api/` are intentionally **not** created now.

## 2. Dependencies (`backend/pyproject.toml`)
- **Runtime:** `python-docx`, `lxml`, `pydantic>=2`, `pydantic-settings`, `click`.
- **Dev:** `pytest`, `pytest-cov`, `ruff`.
- Console script: `praktikit = "praktikit.cli:main"`; also `python -m praktikit`.

## 3. Core design decisions

**Stable IDs.** During parsing, walk `body` children in order; assign `p-/tbl-/img-/sec-` + zero-padded index by encounter. Because mutation runs on a **byte-identical clone** of the source, re-walking assigns the same IDs → plan ops map 1:1. Text is never used as an identifier.

**Ordered block model.** Never iterate `document.paragraphs` / `document.tables` separately. A single pass over `w:body` yields `DocumentBlock` items preserving real order (Paragraph, Table, Image-within-paragraph, SectionBoundary). Each block carries full metadata (para props, run formatting, numbering, page-break flags, image rels).

**Preserve-by-mutation.** `template_generator` copies `source.docx → working.docx`, opens `word/document.xml` with lxml, re-walks to map IDs, and applies each `CleaningOperation` by editing XML in place. All untouched package parts (styles, numbering, theme, settings, headers/footers, rels, media) are left intact. `python-docx` is used for reads and structural ops; **raw lxml** is used for run-preserving text edits (never `paragraph.text = …`).

**Run-level preservation utils (Section 23):** `replace_paragraph_text_preserving_format()`, `clear_paragraph_text_preserving_format()`, `insert_placeholder_preserving_format()` — keep `<w:pPr>`, the first run's `<w:rPr>`, numbering, indents; edit only `<w:t>`.

**Secure parsing.** lxml configured with `resolve_entities=False`, `no_network=True`; zip entry paths validated (no `..`, no absolute) to block traversal; no macro/embedded-object execution; original treated as untrusted.

**Confidence gating (Section 48):** `>=0.90` AUTO · `0.70–0.89` AUTO+FLAG · `<0.70` REVIEW_REQUIRED→default KEEP. Thresholds in config.

## 4. Pipeline (maps to spec Section 9 + Section 91 Steps 1–12)

1. **Validate input** (`validator.py`): ext, MIME, ZIP signature, `[Content_Types].xml`, `word/document.xml`, ≤25 MB (config).
2. **Clone** source → working copy (immutable original).
3. **Parse** (`parser.py` + `package_reader.py`): document-level meta + ordered blocks + runs + tables + images + sections (page size/orientation/margins, header/footer refs).
4. **Style analysis** (`style_analyzer.py`): enumerate styles; build per-paragraph fingerprints for clustering non-Word-styled headings.
5. **Structure detection** (`structure_detector.py`): heading score from structural (style/outlineLvl/numbering), visual (bold/size/uppercase/center/spacing), text (BAB/CHAPTER/1.1/A./I.), and statistical (recurring fingerprint) signals → hierarchy tree + cover region.
6. **Classify** (`semantic_classifier.py`): each block → `SemanticRole` + confidence + reasons (CHAPTER_HEADING, COVER_STATIC/VARIABLE, BODY_CONTENT, TABLE_TEMPLATE/CONTENT, IMAGE_LOGO/CONTENT, CAPTION, REFERENCES_*, APPENDIX_*, PAGE_BREAK, UNKNOWN…). LLM stays a stub `Protocol`.
7. **Detect variables** (`variable_detector.py`): inline `Label : value`, stacked label/value, identity tables → `{{NAMA}}`, `{{NIM}}`, …; unknown → `{{FIELD_n}}`.
8. **Plan** (`cleaning_planner.py`): emit `CleaningPlan` with ops (`KEEP`, `REPLACE_WITH_PLACEHOLDER`, `KEEP_STRUCTURE_CLEAR_CONTENT`, `KEEP_TABLE_STRUCTURE`/`CLEAR_TABLE_DATA`, `REMOVE_CONTENT_IMAGE`, `KEEP_IMAGE`, `REVIEW_REQUIRED`).
9. **Mutate** (`mutation_engine.py`): apply ops to clone, preserving formatting; mode `clean_template` (placeholders) or `personalized` (filled values).
10. **Validate output** (`validator.py`): valid ZIP/XML, rels integrity, reopens in python-docx, headings present, variables applied, image rels intact, margins/sections match source.
11. **Leak check** (`leak_detector.py`): second-pass — compare source BODY_CONTENT vs output, flag shared long sequences (strict mode fails generation).

## 5. Smart placeholders (Section 21, no LLM)
`placeholder.py` maps the nearest heading title to contextual text:
`Latar Belakang → [Tulis latar belakang di sini]`, `Tujuan → [Tuliskan tujuan praktikum]`, `Landasan Teori → …`, `Hasil → [Masukkan hasil praktikum di sini]`, `Pembahasan → [Jelaskan hasil praktikum di sini]`, `Kesimpulan → [Tuliskan kesimpulan]`, `Daftar Pustaka/Referensi → [Tambahkan referensi]`. Fallback: `[Isi {Title} di sini]`.

## 6. CLI (`click`)
- `praktikit analyze <file> [--json out.json] [--debug debug.json]` → summary (sections, paragraphs, tables, images, variables, structure tree).
- `praktikit clean <file> [--output out.docx] [--mode clean_template|personalized] [--strict] [--var KEY=VAL…]` → runs analyze→plan→generate→validate→leak; prints counts (variables replaced, paragraphs cleaned, images removed, tables cleaned) + output path.
- `praktikit --version`. Working files use UUID names under a temp dir; original untouched. Debug JSON dumps blocks, fingerprints, classifications, scores, reasons, decisions.

## 7. Testing strategy
**Fixtures generated programmatically** in `tests/fixtures/builders.py` (no binary blobs) per Section 63: F1 simple BAB structure; F2 custom I./A./B. headings; F3 logo + table + screenshot + footer page-numbering; F4 all-manual formatting (no Word heading styles); F5 cover built from a table.
- **Unit:** input validator, ordered parser + IDs, structure detector (heading/cover/hierarchy), classifier roles+confidence+reasons, variable detector (3 patterns), cleaning planner ops, contextual placeholders, mutation format-preservation, leak detector.
- **Integration `test_end_to_end.py`:** fixture → clean → reopen → assert headings kept, placeholders inserted, old body removed, logo kept, table structure kept/data cleared, margins/sections preserved, original unchanged.
- **Golden `test_golden.py`:** compare structural properties (paper, margins, sections, styles, headings, numbering, header/footer, image count) source vs output — not byte equality.
- **Leak regression `test_leak_regression.py`:** inject `UNIQUE_SECRET_REPORT_SENTENCE_123` as BODY_CONTENT, assert absent from output.

## 8. Documentation & config
- `README.md`: purpose, architecture, prerequisites (uv), setup, run tests, CLI usage, API/frontend marked deferred, known limitations.
- `docs/architecture.md`: pipeline + layer responsibilities + preserve-by-mutation + stable IDs.
- `docs/document-model.md`: internal schema reference.
- `.env.example`: `MAX_UPLOAD_SIZE=25MB`, `SESSION_TTL`, `TEMP_DIRECTORY`, `AI_ENABLED=false`, `CLASSIFICATION_THRESHOLD=0.70`, `STRICT_LEAK_CHECK=true`.

## 9. Definition of done (this plan)
On a real/generated DOCX, both commands succeed and the acceptance scenario (Section 74) holds:
- `praktikit analyze sample.docx` detects cover, BABs, subheadings, variables.
- `praktikit clean sample.docx --output clean-template.docx` yields a **valid, Word-compatible** DOCX where: page size/margins/sections/headings/numbering/page-breaks/header-footer are preserved; identity fields → `{{PLACEHOLDERS}}`; body content → contextual placeholders; content images removed (logo kept); tables cleared but structure kept; original file byte-identical; leak check passes. Full `pytest` suite green.

## 10. Deferred (next plans, per spec sequencing)
FastAPI layer (upload/analyze/generate/download + ProcessingSession), then Next.js stepper UI, then polish (sessions/cleanup, error UX, regression hardening).
