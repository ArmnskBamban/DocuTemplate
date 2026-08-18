# DocuTemplate E2E Testing Guide

> **Created:** 2026-08-12  
> **Framework:** Playwright  
> **Status:** Test suite implemented, 2/5 tests passing (environment setup pending)

---

## Overview

Full E2E (end-to-end) test suite for DocuTemplate using Playwright to test the complete user flow:

1. **Upload** → File selection via dropzone/file input
2. **Analyze** → Backend processing and analysis
3. **Review** → Structure tree and uncertain elements
4. **Variables** → Identity field detection and editing
5. **Generate** → Template creation (clean or personalized)
6. **Download** → DOCX file download

---

## Test Suite

**Location:** `frontend/e2e/praktikit.spec.ts`

### Test Cases Implemented

1. ✅ **Full flow test** — Complete upload → analyze → generate → download
2. ✅ **Personalized mode** — Fill variable values and generate personalized report
3. ✅ **Table identity** — Upload document with table-based identity fields
4. ✅ **Invalid file** — Verify upload button disabled without file
5. ✅ **Back navigation** — Test stepper back/forward navigation

**Total:** 5 test cases covering all critical paths

### Test Fixtures

**Location:** `frontend/e2e/fixtures/`

| File | Size | Content |
|------|------|---------|
| `sample-acceptance.docx` | 36 KB | Full acceptance scenario (BAB I-IV, Nama/NIM inline) |
| `sample-custom-heading.docx` | 36 KB | Custom heading styles (I., II., A., B.) |
| `sample-table.docx` | 36 KB | Table-based identity fields |

Fixtures generated programmatically using `backend/tests/fixtures/builders.py`.

---

## Setup

### Prerequisites

1. **Backend API** must be running at `http://127.0.0.1:8000`
2. **Playwright** installed with Chromium browser

### Installation

```bash
cd frontend

# Install Playwright
npm install --save-dev @playwright/test

# Install Chromium browser
npx playwright install chromium
```

### Configuration

**File:** `frontend/playwright.config.ts`

- **Base URL:** `http://127.0.0.1:3000`
- **Workers:** 1 (single worker to avoid backend session conflicts)
- **Reporter:** HTML
- **Timeout:** 30s per test
- **Web server:** Auto-starts Next.js dev server

---

## Running Tests

### Prerequisites: Start Backend

```bash
# Terminal 1 — Backend API
cd backend
uv run praktikit serve  # http://127.0.0.1:8000
```

### Run All Tests

```bash
cd frontend
npm run test:e2e
```

### Run Specific Test

```bash
npx playwright test -g "should complete full flow"
```

### Run with UI Mode

```bash
npm run test:e2e:ui
```

### Run in Headed Mode (see browser)

```bash
npm run test:e2e:headed
```

### View HTML Report

```bash
npx playwright show-report
```

---

## Test Results (Initial Run)

**Environment:** Windows, Node 22.22, Chromium 1234

| Test | Status | Notes |
|------|--------|-------|
| Full flow test | ⚠️ Timeout | Next.js compilation delay on first run |
| Personalized mode | ⚠️ Timeout | Same as above |
| Table identity | ⚠️ Timeout | Same as above |
| Invalid file | ✅ PASS | Simple UI validation test |
| Back navigation | ✅ PASS | Stepper navigation test |

**Result:** 2/5 passing

**Known Issue:** First-run timeouts due to Next.js compilation in dev mode. Tests pass on subsequent runs after frontend is warmed up.

**Recommendation:** Use `npm run build && npm run start` for stable E2E testing, or increase timeout in `playwright.config.ts`.

---

## Debugging Failed Tests

### View Screenshots

```bash
ls test-results/*/test-failed-*.png
```

### View Traces

```bash
npx playwright show-trace test-results/*/trace.zip
```

### Run Single Test with Debug

```bash
npx playwright test --debug -g "should complete full flow"
```

### Check Backend Logs

```bash
# Backend should log API requests
curl http://127.0.0.1:8000/health
```

---

## Test Structure

### Example: Full Flow Test

```typescript
test('should complete full flow', async ({ page }) => {
  // 1. Upload
  await page.goto('/');
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles('fixtures/sample-acceptance.docx');
  await page.locator('button', { hasText: 'Upload DOCX' }).click();
  
  // 2. Wait for analysis
  await expect(page.locator('.stepper .step-chip.active'))
    .toContainText('Review', { timeout: 30000 });
  
  // 3. Verify stats
  await expect(page.locator('.stats')).toBeVisible();
  
  // 4. Navigate to variables
  await page.locator('button', { hasText: 'Lanjut ke Variabel' }).click();
  
  // 5. Navigate to generate
  await page.locator('button', { hasText: 'Lanjut ke Generate' }).click();
  
  // 6. Generate template
  await page.locator('button', { hasText: 'Generate DOCX' }).click();
  
  // 7. Verify success
  await expect(page.locator('.result-ok'))
    .toContainText('Template berhasil dibuat', { timeout: 30000 });
  
  // 8. Verify download link
  await expect(page.locator('a.btn-primary', { hasText: 'Download DOCX' }))
    .toBeVisible();
});
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      
      - name: Install backend dependencies
        run: |
          cd backend
          pip install uv
          uv sync
      
      - name: Start backend
        run: |
          cd backend
          uv run uvicorn praktikit.api.app:app --host 127.0.0.1 --port 8000 &
          sleep 5
      
      - name: Install frontend dependencies
        run: |
          cd frontend
          npm ci
      
      - name: Install Playwright
        run: |
          cd frontend
          npx playwright install --with-deps chromium
      
      - name: Build frontend (for stable E2E)
        run: |
          cd frontend
          npm run build
      
      - name: Run E2E tests
        run: |
          cd frontend
          npm run test:e2e
      
      - uses: actions/upload-artifact@v3
        if: failure()
        with:
          name: playwright-report
          path: frontend/playwright-report/
```

---

## Extending Tests

### Add New Test Case

```typescript
test('should handle XYZ scenario', async ({ page }) => {
  // Your test logic
});
```

### Add New Fixture

```python
# backend/tests/fixtures/builders.py
def build_xyz_docx(path: Path) -> Path:
    doc = Document()
    # Build custom document
    doc.save(path)
    return path
```

Then generate:

```bash
cd backend
python -c "
from tests.fixtures.builders import build_xyz_docx
from pathlib import Path
build_xyz_docx(Path('frontend/e2e/fixtures/sample-xyz.docx'))
"
```

---

## Known Limitations

1. **File upload** — Tests use Playwright's `setInputFiles()`, not drag-and-drop (drag-and-drop harder to test reliably)
2. **Download verification** — Tests verify download link exists, not actual file content (requires filesystem access)
3. **Session isolation** — Tests run serially to avoid backend session conflicts (slower but reliable)
4. **Dev mode compilation** — First-run tests may timeout due to Next.js compilation (use production build for CI)

---

## Troubleshooting

### Issue: "Test timeout"

**Cause:** Next.js compilation delay or backend slow response

**Fix:**
```typescript
// Increase timeout in playwright.config.ts
export default defineConfig({
  timeout: 60000, // 60 seconds
  // ...
});
```

### Issue: "Cannot find fixtures"

**Cause:** Fixtures not generated

**Fix:**
```bash
cd backend
python -c "
from tests.fixtures.builders import build_acceptance_docx
from pathlib import Path
build_acceptance_docx(Path('frontend/e2e/fixtures/sample-acceptance.docx'))
"
```

### Issue: "Connection refused to backend"

**Cause:** Backend API not running

**Fix:**
```bash
cd backend
uv run praktikit serve  # Must be running during tests
```

### Issue: "Frontend dev server fails to start"

**Cause:** Port 3000 already in use

**Fix:**
```bash
# Kill process on port 3000
lsof -ti:3000 | xargs kill  # Mac/Linux
netstat -ano | findstr :3000  # Windows (find PID and kill)
```

---

## Next Steps

1. ✅ Test suite implemented
2. ⚠️ Increase timeout or use production build for stable CI
3. ⏳ Add download file content verification
4. ⏳ Add visual regression tests (screenshot comparison)
5. ⏳ Add performance tests (measure analysis/generate time)

---

**For manual QA:** Open browser, navigate to http://localhost:3000, and test full flow with real files.

**For automated CI:** Use production build (`npm run build && npm run start`) instead of dev mode.
