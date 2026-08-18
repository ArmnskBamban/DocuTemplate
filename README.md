# DocuTemplate — Smart Report Template Extractor

> **Stop copy laporan senior satu-satu. Upload sekali, dapat template bersih.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-32%2B%20passing-green.svg)]()
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)]()
[![GitHub](https://img.shields.io/github/v/release/ArmnskBamban/DocuTemplate)]()

**DocuTemplate** mengubah laporan praktikum yang sudah jadi (`.docx`) menjadi template bersih yang siap dipakai ulang. Tool ini:

- ✅ **Menjaga format asli** — cover, logo, margins, heading, numbering, page breaks tetap utuh
- ✅ **Menghapus konten lama** — isi laporan dihapus, struktur dan format tetap ada
- ✅ **Ganti data identitas dengan placeholder** — Nama/NIM/Kelas → {{NAMA}}/{{NIM}}/{{KELAS}}
- ✅ **Bekerja otomatis tanpa AI** — 100% deterministik, tidak perlu internet/API key

---

## 🎯 Quick Start (3 Menit) — Untuk User Umum

### 📦 Install & Jalankan dengan Docker (Paling Mudah)

**1. Download & Install Docker**  
Download dari: https://www.docker.com/get-started/

**2. Clone Project**
```bash
git clone https://github.com/ArmnskBamban/DocuTemplate.git
cd DocuTemplate
```

**3. Jalankan**
```bash
docker compose up --build
```

**4. Buka Browser**
```
http://localhost:3000
```

**5. Upload file `.docx` laporan Anda → Download template bersih!**

> **💡 Tidak ingin install Docker?** Lihat [Cara Install Manual](#-install-manual-tanpa-docker) di bawah.

---

## 📋 Contoh Input → Output

### Input (Laporan Lama):
```
═══════════════════════════════════════
LAPORAN PRAKTIKUM DATA MINING

Nama    : John Doe
NIM     : 24100001
Kelas   : TI-A
Modul   : Random Forest

BAB I PENDAHULUAN
1.1 Latar Belakang
Random forest adalah algoritma machine learning...
a) Kelebihan pertama
b) Kelebihan kedua
c) Kelebihan ketiga

1.2 Tujuan
Tujuan praktikum ini adalah...
```

### Output (Template Bersih):
```
═══════════════════════════════════════
LAPORAN PRAKTIKUM DATA MINING

Nama    : {{NAMA}}
NIM     : {{NIM}}
Kelas   : {{KELAS}}
Modul   : {{MODUL}}

BAB I PENDAHULUAN
1.1 Latar Belakang
[Isi Latar Belakang di sini]

1.2 Tujuan
[Isi Tujuan di sini]
```

**Yang Dihapus:** Konten body, list items (`a)`, `b)`, `c)`, `1)`, dll), tabel data  
**Yang Dipertahankan:** Format, heading, struktur, gambar

---

## 🚀 Cara Pakai (Web UI)

Setelah install (via Docker atau manual), buka **http://localhost:3000** dan ikuti 5 langkah:

1. **Upload** — Pilih file `.docx` laporan lama (max 25 MB)
2. **Analisis** — System otomatis analisis struktur
3. **Review** — Cek struktur yang terdeteksi
4. **Variabel** — Edit placeholder untuk data identitas
5. **Generate** — Download template bersih atau personalized

---

## 📋 Cara Install Manual (Tanpa Docker)

### Prerequisite
- ✅ **Python 3.11+** — Download: https://www.python.org/downloads/
- ✅ **Node.js 20+** — Download: https://nodejs.org/

### Windows
```cmd
# Clone project
git clone https://github.com/ArmnskBamban/DocuTemplate.git
cd DocuTemplate

# Install backend (Terminal 1)
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# Install frontend (Terminal 2)
cd ../frontend
npm install
```

### macOS / Linux
```bash
# Clone project
git clone https://github.com/ArmnskBamban/DocuTemplate.git
cd DocuTemplate

# Install backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Install frontend
cd ../frontend
npm install
```

### Jalankan
```bash
# Backend (Terminal 1)
cd backend
.venv/bin/python -m uvicorn praktikit.api.app:app --host 127.0.0.1 --port 8000

# Frontend (Terminal 2)
cd frontend
npm run dev
```

Buka: **http://localhost:3000**

---

## 💻 CLI (Command Line) — untuk User Advanced

```bash
# Install (sudah termasuk saat docker/manual install)
cd backend
pip install -e ".[dev]"

# Analyze laporan
uv run praktikit analyze laporan.docx

# Generate template
uv run praktikit clean laporan.docx --output template.docx

# Personalized (isi data Anda)
uv run praktikit clean laporan.docx \
  --output laporan-saya.docx \
  --var NAMA "Jiyad Rifqi" \
  --var NIM "2411533003" \
  --var KELAS "TI-3A"
```

---

## 🔧 API & Docker — untuk Developer

**REST API Documentation:** http://localhost:8000/docs (Swagger UI)

**Docker Deployment:**
```bash
# Development
docker compose up --build

# Production
docker compose -f docker-compose.prod.yml up -d
```

Lihat [`DEPLOYMENT.md`](DEPLOYMENT.md) untuk panduan lengkap.

---

## 📋 Contoh Input → Output

### Input (Laporan Lama):
```
═══════════════════════════════════════
LAPORAN PRAKTIKUM DATA MINING

Nama    : John Doe
NIM     : 24100001
Kelas   : TI-A
Modul   : Random Forest

BAB I PENDAHULUAN
1.1 Latar Belakang
Random forest adalah algoritma machine learning...
a) Kelebihan pertama
b) Kelebihan kedua
c) Kelebihan ketiga

1.2 Tujuan
Tujuan praktikum ini adalah...

BAB II LANDASAN TEORI
2.1 Pengertian Random Forest
Random forest merupakan...

[Tabel hasil eksperimen dengan data lama]
═══════════════════════════════════════
```

### Output (Template Bersih):
```
═══════════════════════════════════════
LAPORAN PRAKTIKUM DATA MINING

Nama    : {{NAMA}}
NIM     : {{NIM}}
Kelas   : {{KELAS}}
Modul   : {{MODUL}}

BAB I PENDAHULUAN
1.1 Latar Belakang
[Isi Latar Belakang di sini]

1.2 Tujuan
[Isi Tujuan di sini]

BAB II LANDASAN TEORI
2.1 Pengertian Random Forest
[Isi Pengertian Random Forest di sini]

[Tabel hasil eksperimen dihapus - siap diisi baru]
═══════════════════════════════════════
```

**Yang Dihapus:**
- ✅ Semua konten teks body (paragraf isi)
- ✅ List items (`a)`, `b)`, `c)`, `1)`, `2)`, dll)
- ✅ Tabel data/konten
- ✅ Data identitas lama

**Yang Dipertahankan:**
- ✅ Format & styling (bold, italic, font, ukuran)
- ✅ Struktur heading (BAB I, 1.1, 1.2, dll)
- ✅ Margins, page breaks, header/footer
- ✅ Gambar (posisi & ukuran preserved)
- ✅ Tabel identitas (dengan placeholder)

---

## 💻 Cara Pakai (Command Line)

Untuk pengguna advanced atau automation:

```bash
# Masuk ke folder backend
cd backend

# Install dependencies (sekali saja)
uv sync --extra dev

# Analisis laporan (lihat struktur)
uv run praktikit analyze path/to/Laporan_Praktikum.docx

# Generate template bersih
uv run praktikit clean path/to/Laporan_Praktikum.docx \
    --output template-bersih.docx

# Generate dengan data Anda (personalized)
uv run praktikit clean laporan-lama.docx \
    --output laporan-saya.docx \
    --var NAMA "Jiyad Rifqi" \
    --var NIM "2411533003" \
    --var KELAS "TI-3A" \
    --var MODUL "Random Forest"

# Output JSON untuk debugging
uv run praktikit analyze laporan.docx \
    --json analysis.json \
    --debug debug.json
```

---

## 🔧 API (Untuk Integration)

Jika Anda ingin integrate ke aplikasi lain:

```bash
# Start API server
cd backend
uv run praktikit serve  # Akses: http://127.0.0.1:8000
```

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/documents/analyze` | Analyze DOCX file |
| `POST` | `/api/documents/{id}/generate` | Generate template |
| `GET` | `/api/documents/{id}/download` | Download hasil |
| `DELETE` | `/api/documents/{id}` | Cleanup session |
| `GET` | `/health` | Health check |

**API Documentation (Interactive):**
```
http://127.0.0.1:8000/docs
```

**Example cURL:**

```bash
# 1. Upload & analyze
curl -X POST http://127.0.0.1:8000/api/documents/analyze \
  -F "file=@laporan.docx" \
  -F "mode=analyze"

# Response:
# {
#   "document_id": "abc123...",
#   "analysis": {
#     "summary": {"paragraphs": 50, "tables": 2, "images": 3},
#     "headings": [{"title": "BAB I", "level": 0}, ...],
#     "variables": [{"label": "Nama", "value": "John", ...}]
#   }
# }

# 2. Generate template
curl -X POST http://127.0.0.1:8000/api/documents/abc123/generate \
  -H "Content-Type: application/json" \
  -d '{"mode": "clean_template"}'

# 3. Download
curl -X GET http://127.0.0.1:8000/api/documents/abc123/download \
  -o template.docx
```

---

## 📦 Docker Deployment

**Quick start (all platforms):**

```bash
docker compose up --build

# Frontend: http://localhost:3000
# API: http://localhost:3000/api
# API Docs: http://localhost:3000/api/docs
```

**Production deployment:**

```bash
docker compose -f docker-compose.prod.yml up -d
```

See [`DOCKER-README.md`](DOCKER-README.md) dan [`DEPLOYMENT.md`](DEPLOYMENT.md) untuk konfigurasi production.

---

## ✨ Fitur Detail

### 1. Smart Detection

| Element | Detected As | Action |
|---------|------------|--------|
| Cover page | COVER_STATIC | Preserved |
| Heading (BAB I, 2.1, 2.3.1) | SECTION_HEADING | Preserved |
| Body text | BODY_CONTENT | Cleared |
| List items (a), b), 1), 10)) | INSTRUCTION_TEXT | Removed |
| Data tables | TABLE_CONTENT | Removed |
| Identity table (Nama\|John) | TABLE_IDENTITY | Preserved + placeholder |
| Images (logo) | IMAGE_LOGO | Preserved |
| Images (content) | IMAGE_CONTENT | Preserved |

### 2. Placeholder Mapping

Auto-detect dan mapping ke placeholder:

```
"Nama" / "Name" → {{NAMA}}
"NIM" / "Student ID" → {{NIM}}
"Kelas" / "Class" → {{KELAS}}
"Modul" / "Module" → {{MODUL}}
"Tanggal" / "Date" → {{TANGGAL}}
"Asisten" / "Assistant" → {{ASISTEN}}
... (dan lebih banyak)
```

### 3. Leak Prevention

Mencegah konten lama "bocor" ke template:

- Second-pass comparison antara source & output
- Deteksi text shingle similarity
- Mode strict: tolak jika ada bocor

```bash
uv run praktikit clean laporan.docx --output out.docx --no-strict
```

---

## 📋 Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.11+ |
| Node.js | 20+ (frontend only) |
| Docker | 20.10+ (optional) |
| Disk space | ~500 MB untuk project + dependencies |
| RAM | 2 GB minimum |

---

## 📚 Documentation

| Document | Untuk | Isi |
|----------|-------|-----|
| **[`docs/architecture.md`](docs/architecture.md)** | Developer | Arsitektur system, design principles, pipeline flow |
| **[`docs/document-model.md`](docs/document-model.md)** | Developer | Pydantic models, data structure |
| **[`DEPLOYMENT.md`](DEPLOYMENT.md)** | DevOps/Admin | Production setup, security, troubleshooting |
| **[`DOCKER-README.md`](DOCKER-README.md)** | DevOps/Admin | Docker quick start |
| **[`handoff.md`](handoff.md)** | Developer | Project overview, file reference, known issues |

---

## 🛠️ Development

### Setup

```bash
# Backend
cd backend
uv sync --extra dev

# Frontend
cd frontend
npm install
```

### Run Tests

```bash
cd backend
uv run pytest -q          # 32+ tests
```

### Run Locally

```bash
# Terminal 1 - Backend
cd backend
uv run praktikit serve

# Terminal 2 - Frontend
cd frontend
npm run dev
```

### Build Frontend (Static Export)

```bash
cd frontend
npm run build
```

---

## ⚡ Performance

| Operation | Time |
|-----------|------|
| Analyze 50-page DOCX | ~1 second |
| Generate template | ~0.5 second |
| File download | <100 ms |
| **Total end-to-end** | ~2-3 seconds |

*Tested on Intel i7 + 16GB RAM*

---

## 🐛 Known Issues

1. **Playwright E2E timeouts** — First run di dev mode lambat karena Next.js compile; stable dengan production build
2. **Hydration mismatch warning** — Browser extensions inject attributes; tidak affect functionality
3. **Windows: port 8000 conflict** — Jika 2 backend jalan bersamaan, gunakan `Get-Process python | Stop-Process -Force`

---

## 🔒 Security

- ✅ Original file never modified (works on clone only)
- ✅ No external API calls
- ✅ No LLM/AI dependency
- ✅ Hardened ZIP parser (prevent traversal)
- ✅ No PII in logs
- ✅ Encrypted session store (optional)

---

## 💡 Tips & Tricks

### Batch Processing (CLI)

```bash
# Process multiple files
for file in reports/*.docx; do
    uv run praktikit clean "$file" \
        --output "templates/${file%.docx}-template.docx"
done
```

### Integration ke School System

```bash
# Upload ke learning management system setelah generate
curl -X POST https://your-lms.edu/api/upload \
  -F "file=@template.docx" \
  -H "Authorization: Bearer $TOKEN"
```

### Custom Placeholder Mapping

Edit `backend/src/praktikit/services/docx/placeholder.py` untuk tambah placeholder custom:

```python
KNOWN_FIELDS = {
    "Nama": "{{NAMA}}",
    "NIM": "{{NIM}}",
    "Your Custom Field": "{{CUSTOM}}"  # Tambah di sini
}
```

---

## 📞 Support

**Questions atau bug reports?**

1. Check [`handoff.md`](handoff.md) untuk architecture walkthrough
2. Lihat [`docs/`](docs/) untuk detailed documentation
3. Run dengan `--debug` flag untuk detailed logs

```bash
uv run praktikit analyze laporan.docx --debug debug.json
```

---

## 📄 License

MIT — Bebas pakai untuk project pribadi maupun komersial

---

## 🙌 Credits

Built with:
- **Python 3.11** — Core engine
- **FastAPI** — REST API
- **Next.js** — Frontend UI
- **python-docx** — DOCX manipulation
- **Pydantic** — Data validation

---

**Happy template making! 🚀**
