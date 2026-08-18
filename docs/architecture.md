# DocuTemplate Architecture

> **Last Updated:** 2026-08-12  
> **Version:** 0.1.0 (Core Engine + CLI + API + Frontend)

---

## Table of Contents

1. [Overview](#overview)
2. [Design Principles](#design-principles)
3. [System Architecture](#system-architecture)
4. [Core Pipeline](#core-pipeline)
5. [Layer Responsibilities](#layer-responsibilities)
6. [Data Flow](#data-flow)
7. [Security Model](#security-model)
8. [Extensibility](#extensibility)

---

## Overview

DocuTemplate is a **Smart Report Template Extractor** that transforms a finished practicum report (`.docx`) into a clean, reusable template by:

1. **Preserving** document structure and formatting (cover, logo, margins, headings, numbering, styles)
2. **Removing** the previous report's specific content (body text, data tables, screenshots)
3. **Replacing** identity fields (Nama, NIM, Kelas) with placeholders ({{NAMA}}, {{NIM}}, {{KELAS}})

### Core Value Proposition

> **Stop copying senior reports paragraph-by-paragraph. Upload once, get a clean template.**

### What It Is NOT

- NOT an automatic report writer
- NOT a plagiarism tool
- NOT dependent on LLMs (core works 100% deterministically)

---

## Design Principles

### 1. Preserve by Mutation, Not Reconstruction

**Never rebuild a DOCX from scratch.** The source file is cloned byte-for-byte, and only elements that need cleaning are mutated in place via raw OOXML manipulation.

**Why:** Microsoft Word documents contain hundreds of subtle formatting details (styles, numbering definitions, theme colors, embedded fonts, headers/footers, relationships) that are impossible to reconstruct perfectly. Rebuilding from scratch would lose:
- Custom styles and themes
- Numbering scheme definitions
- Header/footer content
- Embedded media relationships
- Document-level settings

**Implementation:** `MutationEngine` reads `word/document.xml`, builds an ID map by walking `w:body`, applies mutations, writes back mutated XML while preserving all other parts.

### 2. Stable Positional IDs

During parsing, every element is assigned a **stable ID** based on its position in `w:body`:
- `p-000001`, `p-000002`, ... (paragraphs)
- `tbl-000001`, `tbl-000002`, ... (tables)
- `img-000001`, `img-000002`, ... (images)
- `sec-000001`, `sec-000002`, ... (section boundaries)

**Why stability matters:** Because mutation operates on a byte-identical clone of the source, re-walking the clone assigns identical IDs. This allows the `CleaningPlan` to reference elements by ID, and the `MutationEngine` to resolve them 1:1.

**Never use paragraph text as an identifier** — text changes during mutation.

### 3. Ordered Block Model

**Never iterate `document.paragraphs` and `document.tables` separately.** The parser walks `w:body` children once in element order, yielding `DocumentBlock` items:

```
Paragraph → Paragraph → Table → Paragraph → (Image within paragraph) → SectionBoundary → ...
```

**Why:** OOXML's `w:body` is a sequence. Iterating collections separately loses order and makes it impossible to:
- Detect cover/body boundaries accurately
- Associate images with their enclosing paragraphs
- Build heading hierarchy correctly
- Preserve section break positions

### 4. Confidence-Gated Automation

Every classification carries a confidence score (0.0–1.0). The automation mode is determined by thresholds:

| Confidence | Automation | Behavior |
|------------|------------|----------|
| ≥ 0.90 | `AUTO` | Apply automatically, no user review needed |
| 0.70–0.89 | `REVIEW` | Apply automatically but flag for user review in UI |
| < 0.70 | `KEEP` | Never destructive, require explicit user decision |

**Thresholds are configurable** via environment variables (`AUTO_THRESHOLD`, `REVIEW_THRESHOLD`).

**Why:** Academic documents vary widely in structure. Confidence gating allows the system to:
- Act confidently on high-signal cases (e.g., paragraph with "BAB I" in Heading 1 style)
- Flag medium-confidence cases for quick review (e.g., centered bold text without style)
- Preserve low-confidence elements safely (unknown formatting patterns)

### 5. No-LLM Baseline

The core engine works **fully without any LLM**. All detection is deterministic heuristics:

#### Heading Detection Signals
- **Structural:** Word Heading style, outline level
- **Visual:** bold, font size ≥ 13pt, uppercase, centered alignment
- **Text:** BAB/CHAPTER patterns, decimal numbering (1.1, 1.1.1), roman numerals (I, II, III)
- **Statistical:** fingerprint clustering (paragraphs with identical formatting)

#### Variable Detection Patterns
- **Inline:** `Nama : John Doe` on single paragraph
- **Stacked:** `Nama` on one paragraph, `John Doe` on next
- **Table:** Two-column table with label column and value column

#### Semantic Classification
- Position-based (cover vs body region)
- Role-based (heading, content, caption, references, appendix)
- Content-based (keyword matching for cover static text)

**Optional LLM layer** is defined as a `Protocol` interface but not implemented. When added, it will supplement heuristics for low-confidence cases only.

### 6. Security by Design

- **Original file is immutable** — all work on clones
- **ZIP traversal prevention** (no `..` in entry paths)
- **Hardened XML parser** (`resolve_entities=False`, `no_network=True`, `load_dtd=False`)
- **No macro/embedded object execution**
- **No external resource fetching**
- **No PII in logs** — only session IDs, counts, durations (spec Section 11)

---

## System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web UI (Next.js)                          │
│        Upload → Analisis → Review → Variabel → Generate         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    REST API (FastAPI)                            │
│      POST /analyze · POST /{id}/generate · GET /download         │
│              + SessionStore (in-memory + temp dirs)              │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌───────────────────┐       ┌──────────────┐
        │  CLI              │       │  Template    │
        │  analyze / clean  │       │  Generator   │
        └───────────────────┘       └──────────────┘
                                            │
        ┌───────────────────────────────────┴───────────────┐
        ▼                                                   ▼
┌─────────────────┐                              ┌─────────────────┐
│  Detection      │                              │  Mutation       │
│  Layer          │                              │  Layer          │
│  (structure,    │                              │  (mutation      │
│   semantic,     │◄──────────────────────────┐  │   engine)       │
│   variables,    │                           │  │                 │
│   cleaning)     │                           │  └─────────────────┘
└─────────────────┘                           │
        │                                      │
        ▼                                      │
┌─────────────────┐                           │
│  Parser         │                           │
│  (ordered       │                           │
│   blocks,       │───────────────────────────┘
│   stable IDs)   │
└─────────────────┘
        │
        ▼
┌─────────────────┐
│  Validator      │
│  (secure input) │
└─────────────────┘
        │
        ▼
   word/document.xml
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 16 + TypeScript | Static export stepper UI |
| **API** | FastAPI 0.141 + uvicorn | REST endpoints, session management |
| **Core Engine** | Python 3.11+ | DOCX processing pipeline |
| **OOXML Parsing** | python-docx + lxml | High-level API + raw XML access |
| **Data Models** | Pydantic v2 | Type-safe schemas with validation |
| **CLI** | Click 8.1 | Command-line interface |
| **Testing** | pytest 8.0 | Unit + integration tests |
| **Deployment** | Docker + nginx | Containerized full stack |

---

## Core Pipeline

### Analyze Phase

```
INPUT: source.docx
    │
    ▼
┌─────────────────┐
│  VALIDATE       │  • Check extension, MIME, ZIP signature
└─────────────────┘  • Verify required parts ([Content_Types].xml, word/document.xml)
    │                • Reject encrypted/oversized files
    ▼
┌─────────────────┐
│  PARSE          │  • Walk w:body in order, assign stable IDs
└─────────────────┘  • Extract document-level meta (page, margins, sections, styles)
    │                • Build blocks: paragraphs, tables, images, section boundaries
    ▼                • Extract run-level formatting
┌─────────────────┐
│  DETECT         │  • Heading detection (style + visual + text + statistical signals)
│  STRUCTURE      │  • Cover region detection (before first "BAB" heading)
└─────────────────┘  • Build hierarchy tree (cover → chapters → sections)
    │
    ▼
┌─────────────────┐
│  CLASSIFY       │  • Assign SemanticRole to each block
│  SEMANTICS      │  • Compute confidence scores
└─────────────────┘  • Determine automation level (AUTO/REVIEW/KEEP)
    │
    ▼
┌─────────────────┐
│  DETECT         │  • Inline patterns: "Nama : John"
│  VARIABLES      │  • Stacked patterns: "Nama" / "John"
└─────────────────┘  • Table patterns: | Nama | John |
    │                • Map to standard placeholders ({{NAMA}}, {{NIM}})
    ▼
┌─────────────────┐
│  PLAN           │  • Build CleaningPlan from analysis
└─────────────────┘  • One CleaningOperation per block
    │                • Contextual placeholders based on section heading
    ▼
OUTPUT: AnalysisResult + CleaningPlan
```

### Generate Phase

```
INPUT: source.docx + CleaningPlan + variable_values (optional)
    │
    ▼
┌─────────────────┐
│  CLONE          │  Copy source → working.docx (byte-identical)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  RESOLVE        │  For personalized mode:
│  VARIABLES      │  Replace placeholders in plan with actual values
└─────────────────┘  {{NAMA}} → "Jiyad", {{NIM}} → "24100001"
    │
    ▼
┌─────────────────┐
│  MUTATE         │  • Read word/document.xml from working.docx
└─────────────────┘  • Build ID map by walking w:body (same order as parser)
    │                • Apply CleaningOperations via raw OOXML edits
    ▼                • Write back mutated XML
┌─────────────────┐  • All other parts preserved byte-for-byte
│  VALIDATE       │  • Check ZIP integrity
└─────────────────┘  • Verify relationships intact
    │                • Re-open with python-docx
    ▼
┌─────────────────┐
│  LEAK CHECK     │  • Compare source BODY_CONTENT vs output paragraphs
└─────────────────┘  • Flag shared long text sequences (shingle overlap ≥ 0.6)
    │                • Strict mode: refuse generation if leaks detected
    ▼
OUTPUT: clean-template.docx (or personalized.docx)
```

---

## Layer Responsibilities

### 1. Core Layer

**Location:** `backend/src/praktikit/core/`

| Component | Purpose |
|-----------|---------|
| `config.py` | Environment-based settings (Pydantic) |
| `exceptions.py` | Domain exception hierarchy |
| `logging.py` | Structured, privacy-safe logging |

**Key Principle:** No business logic here — only shared utilities and configuration.

### 2. Models Layer

**Location:** `backend/src/praktikit/models/`

All models use Pydantic v2 for validation and serialization.

| Model | Purpose |
|-------|---------|
| `document.py` | Page layout, margins, sections, styles |
| `blocks.py` | Ordered block union: `ParagraphBlock | TableBlock | SectionBoundary` |
| `runs.py` | Run-level formatting (font, bold, italic, color) |
| `structure.py` | Detected headings, hierarchy tree |
| `classification.py` | Semantic roles, confidence, automation |
| `variables.py` | Identity fields, placeholders, locations |
| `cleaning.py` | Cleaning plan, operations, actions |
| `analysis.py` | Complete analysis result |

**Key Principle:** Models are pure data — no I/O, no side effects.

### 3. Services Layer

**Location:** `backend/src/praktikit/services/docx/`

#### Input Processing
- `validator.py` — Secure input validation (ZIP, size, encryption)
- `package_reader.py` — Secure OOXML package access, hardened XML parser

#### Parsing
- `parser.py` — **Ordered block parser**, assigns stable IDs, extracts formatting
- `style_analyzer.py` — Fingerprinting, clustering for non-styled headings

#### Detection
- `structure_detector.py` — Heading detection, cover boundary, hierarchy building
- `semantic_classifier.py` — Heuristic role assignment with confidence
- `variable_detector.py` — Identity field detection (inline/stacked/table)

#### Planning
- `placeholder.py` — Contextual placeholder mapping (no LLM)
- `cleaning_planner.py` — Builds `CleaningPlan` from analysis

#### Mutation
- `mutation_engine.py` — **Preserve-by-mutation** via raw OOXML
- `leak_detector.py` — Second-pass content comparison

#### Orchestration
- `template_generator.py` — **Main entry point**, coordinates full pipeline

**Key Principle:** Services are stateless (except `MutationEngine` which holds a working file path).

### 4. CLI Layer

**Location:** `backend/src/praktikit/cli.py`

Commands:
- `praktikit analyze <file>` — Analysis with JSON output
- `praktikit clean <file>` — Template generation
- `praktikit serve` — Start uvicorn API server

**Key Principle:** Thin wrapper over `TemplateGenerator`, handles I/O and formatting.

### 5. API Layer

**Location:** `backend/src/praktikit/api/`

| Component | Purpose |
|-----------|---------|
| `app.py` | FastAPI app factory, CORS, health checks |
| `routes/documents.py` | REST endpoints (analyze, generate, download, delete) |
| `schemas.py` | Request/response Pydantic models |
| `storage/session_store.py` | In-memory session registry + temp dirs |

**Endpoints:**
- `POST /api/documents/analyze` — Upload & analyze
- `POST /api/documents/{id}/generate` — Generate template
- `GET /api/documents/{id}/download` — Download result
- `DELETE /api/documents/{id}` — Cleanup session
- `GET /health` — Health check

**Key Principle:** API layer is stateless; state lives in `SessionStore` with TTL expiry.

### 6. Frontend Layer

**Location:** `frontend/`

| Component | Purpose |
|-----------|---------|
| `src/app/page.tsx` | Stepper UI (5 steps) |
| `src/lib/api.ts` | Typed API client |
| `src/app/globals.css` | Plain CSS design system |

**Steps:**
1. Upload → file selection + drag & drop
2. Analisis → summary stats, detected headings
3. Review → structure tree, uncertain elements
4. Variabel → editable placeholders
5. Generate → clean template vs personalized

**Key Principle:** Frontend is stateless (session ID in URL/state), all processing server-side.

---

## Data Flow

### Object Lifecycle (Analyze)

```
source.docx (bytes)
    │
    ▼
[Validator] → Path
    │
    ▼
[DocxParser] → ParseOutput {
    document_meta: DocumentMeta,
    blocks: list[DocumentBlock],
    styles_by_id: dict[str, StyleInfo]
}
    │
    ▼
[StructureDetector] → StructureDetection {
    heading_info: list[HeadingInfo],
    structure_tree: list[StructureNode],
    cover_end_index: int
}
    │
    ▼
[HeuristicSemanticClassifier] → dict[block_id, Classification]
    │
    ▼
[VariableDetector] → list[VariableField]
    │
    ▼
[CleaningPlanner] → CleaningPlan {
    operations: list[CleaningOperation],
    notes: list[str],
    warnings: list[str]
}
    │
    ▼
AnalysisResult (returned to CLI/API/Frontend)
```

### Object Lifecycle (Generate)

```
source.docx + CleaningPlan + variable_values
    │
    ▼
[MutationEngine.clone_to_working()] → working.docx (temp file)
    │
    ▼
[MutationEngine.apply(plan)] →
    • Read word/document.xml
    • Build ID map (p-000001 → <w:p> element)
    • For each operation:
        - Resolve target element
        - Apply mutation (replace_text, clear_table, remove_image, etc.)
    • Write mutated XML back
    │
    ▼
working.docx (mutated)
    │
    ▼
[Validator.validate_docx_file(working)] → integrity check
    │
    ▼
[LeakDetector.detect(source, working)] → list[leaked_fragments]
    │
    ▼ (if strict_leak_check and leaks → raise LeakDetectedError)
    │
    ▼
working.docx → copy to output_path
    │
    ▼
GenerationResult (returned to CLI/API)
```

---

## Security Model

### Input Validation (Defense in Depth)

1. **Extension check** — Reject `.doc`, `.pdf` early
2. **Size check** — Reject files > `MAX_UPLOAD_SIZE` (default 25MB)
3. **ZIP signature** — Verify `PK\x03\x04` header
4. **ZIP traversal** — Reject paths with `..` or absolute paths
5. **Encryption check** — Reject password-protected files
6. **Required parts** — Verify `[Content_Types].xml` and `word/document.xml` exist

### XML Parsing Hardening

```python
_PARSER = etree.XMLParser(
    resolve_entities=False,  # Block XXE attacks
    no_network=True,         # Block SSRF
    load_dtd=False,          # Block DTD-based attacks
)
```

### Privacy Protection (No PII in Logs)

**Never logged:**
- Original file content
- Variable original values (e.g., student name, NIM)
- Paragraph text content
- Document title / core properties

**Logged safely:**
- Session IDs (UUID hex)
- Counts (paragraphs, tables, variables)
- Confidence scores
- Block IDs (positional, e.g., `p-000042`)
- Duration metrics

### Temporary File Isolation

- Each session gets an isolated temp directory: `praktikit_{uuid}_/`
- Original filename never used as path (prevents path injection)
- Internal filenames randomized: `source_{uuid}.docx`
- Cleanup on session delete or TTL expiry
- No permanent storage of uploads

---

## Extensibility

### Adding a New Semantic Role

1. Add enum value to `SemanticRole` in `models/classification.py`
2. Add detection logic to `HeuristicSemanticClassifier.classify_all()`
3. Add action mapping in `CleaningPlanner._decide_action()`
4. Add mutation logic (if needed) to `MutationEngine._apply_op()`
5. Update tests

### Adding an LLM Classifier

The system defines a `SemanticClassifier` Protocol:

```python
class SemanticClassifier(Protocol):
    def classify_all(
        self,
        blocks: list[DocumentBlock],
        headings: list[HeadingInfo],
        structure_tree: list[StructureNode],
        cover_end_index: int,
    ) -> dict[str, Classification]: ...
```

To add an LLM classifier:

1. Implement the protocol (e.g., `LlmSemanticClassifier`)
2. Use it as a fallback for low-confidence classifications
3. Set `AI_ENABLED=true` in config
4. Never send PII (use `VariableField.safe_view()`)

### Adding a New Detection Pattern

Example: Detect "DAFTAR ISI" (Table of Contents) heading.

1. Add pattern to `structure_detector.py`:
   ```python
   _TOC_RE = re.compile(r"^\s*DAFTAR\s+ISI\s*$", re.IGNORECASE)
   ```
2. Add role to `SemanticRole`: `TOC_HEADING = "toc_heading"`
3. Add classification logic in `semantic_classifier.py`
4. Add action in `cleaning_planner.py`: `KEEP` (preserve TOC)

### Adding a Database Layer

Current: In-memory `SessionStore` with temp dirs.

Future (Phase 4):
1. Define SQLAlchemy models (or equivalent ORM)
2. Add `saved_templates` table
3. Implement `TemplateRepository` with CRUD operations
4. Add authentication/authorization layer
5. Update API routes for `/templates` resource
6. Migrate session store to Redis (for horizontal scaling)

---

## Performance Characteristics

### Throughput

| Document Size | Parse Time | Generate Time | Total Time |
|---------------|------------|---------------|------------|
| 5 pages | ~200ms | ~300ms | ~500ms |
| 15 pages | ~500ms | ~800ms | ~1.3s |
| 50 pages | ~1.5s | ~2.5s | ~4s |

*Measured on Python 3.11, Intel i5, 8GB RAM*

### Memory Usage

- **Parsing:** ~2MB per page (DOM in memory)
- **Mutation:** +1× document size (clone in temp dir)
- **Session store:** ~5MB per active session (includes analysis result)

### Bottlenecks

1. **OOXML parsing** (lxml) — largest contributor
2. **Fingerprint clustering** — O(n²) in worst case for n paragraphs
3. **Leak detection** — shingle comparison is O(n×m) for n source paragraphs, m output paragraphs

**Optimizations applied:**
- Fingerprints cached during structure detection
- Leak detector compares only BODY_CONTENT-classified paragraphs (not headings/labels)
- Mutation engine builds ID map once

---

## Testing Strategy

### Unit Tests

- Individual parsers, detectors, classifiers
- Model validation
- Utility functions (text normalization, shingles)

### Integration Tests

- End-to-end pipeline (source → analysis → generate → validation)
- Layout preservation (margins, page size, sections)
- Determinism (same input → same output IDs)
- Leak detection regression

### API Tests

- Full REST flow (upload → analyze → generate → download)
- Personalized mode with variable substitution
- Error cases (invalid file, missing session, leak detected)

**Total: 32+ tests passing**

---

## Deployment Architecture

See [`DEPLOYMENT.md`](../DEPLOYMENT.md) for full details.

**Production stack:**
```
Internet → nginx/Traefik (HTTPS termination)
           └→ praktikit-frontend (nginx:alpine, static Next.js)
                └→ /api/* → praktikit-backend (FastAPI + uvicorn)
```

**Key features:**
- Docker multi-stage builds (minimal runtime images)
- Health checks (both containers)
- Same-origin API proxy (zero CORS issues)
- Environment-based configuration
- Horizontal scaling ready (with sticky sessions or Redis store)

---

## Future Enhancements

### Phase 4 Roadmap

1. **Database layer** (SQLite dev / PostgreSQL prod) for saved templates
2. **Optional LLM classifier** for low-confidence classifications
3. **Template library** with search and filtering
4. **Batch processing** (multiple files)
5. **Template versioning** and diff view
6. **User authentication** for multi-user deployment
7. **Report format linter** (check required sections, formatting consistency)

### Possible Extensions

- **PDF support** (via pdf2docx or docx2pdf round-trip)
- **Legacy `.doc` support** (via LibreOffice conversion)
- **Real-time collaboration** (WebSocket updates during processing)
- **Template customization** (add/remove sections, change placeholders)
- **Export to other formats** (Markdown, LaTeX)

---

## References

- [Document Model Reference](./document-model.md)
- [Deployment Guide](../DEPLOYMENT.md)
- [Project Handoff](../handoff.md)
- [OOXML Specification](http://officeopenxml.com/)
- [python-docx Documentation](https://python-docx.readthedocs.io/)

---

**Questions or contributions?** See `handoff.md` for codebase walkthrough and key files.
