# Docker Deployment Testing Checklist

> **Purpose:** Verify Docker deployment works correctly before production
> **Prerequisite:** Machine with Docker Desktop or Docker Engine installed

---

## Pre-Deployment Verification

### ✅ Environment Check

```bash
# Verify Docker installation
docker --version
# Expected: Docker version 20.10+

docker compose version
# Expected: Docker Compose version v2.0+

# Check available disk space (need ~2GB)
df -h  # Linux/Mac
# or
wmic logicaldisk get size,freespace,caption  # Windows
```

---

## Phase 1: Build Test

### Step 1: Backend Build

```bash
cd D:/Zcode/project7/backend
docker build -t praktikit-backend:test .
```

**Expected output:**
- ✅ Both stages complete (builder + runtime)
- ✅ No Python import errors
- ✅ Final image size < 200MB

**Verify:**
```bash
docker images | grep praktikit-backend
# Should show: praktikit-backend test ... ~150MB ... seconds ago
```

### Step 2: Frontend Build

```bash
cd D:/Zcode/project7/frontend
docker build -t praktikit-frontend:test .
```

**Expected output:**
- ✅ npm ci succeeds (all dependencies installed)
- ✅ npm run build succeeds (Next.js static export)
- ✅ nginx image created
- ✅ Final image size < 50MB

**Verify:**
```bash
docker images | grep praktikit-frontend
# Should show: praktikit-frontend test ... ~25-30MB ... seconds ago
```

### Step 3: Manual Container Test (Optional)

**Test backend standalone:**
```bash
docker run -d --name test-backend -p 8000:8000 praktikit-backend:test
docker logs -f test-backend
# Look for: "Uvicorn running on http://0.0.0.0:8000"
curl http://localhost:8000/health
# Expected: {"status":"ok"}
docker stop test-backend && docker rm test-backend
```

**Test frontend standalone:**
```bash
docker run -d --name test-frontend -p 8080:80 praktikit-frontend:test
curl http://localhost:8080
# Expected: HTML content (Next.js app)
docker stop test-frontend && docker rm test-frontend
```

---

## Phase 2: Development Deployment

### Step 1: Start Services

```bash
cd D:/Zcode/project7
docker compose up --build
```

**Watch for:**
- ✅ Both services build successfully
- ✅ Backend health check passes (shows "healthy" in logs)
- ✅ Frontend starts after backend (dependency)
- ✅ No CORS errors in backend logs

**Expected final output:**
```
praktikit-backend   | INFO:     Uvicorn running on http://0.0.0.0:8000
praktikit-frontend  | /docker-entrypoint.sh: Configuration complete; ready for start up
```

### Step 2: Health Checks

Open new terminal:

```bash
# Check container status
docker compose ps
# Both should show "healthy" status after ~30 seconds

# Test backend health (via frontend proxy)
curl http://localhost:3000/health
# Expected: {"status":"ok"}

# Test API docs
curl http://localhost:3000/api/docs
# Expected: HTML (Swagger UI)
```

### Step 3: Frontend Access

**Open browser:**
- Navigate to: http://localhost:3000
- ✅ Page loads without errors
- ✅ Hero text visible: "DocuTemplate - Smart Report Template Extractor"
- ✅ Stepper chips visible (Upload, Analisis, Review, Variabel, Generate)
- ✅ Dropzone visible
- ✅ "Upload untuk Mulai" button disabled (no file selected)

**Check browser console (F12):**
- ✅ No CORS errors
- ✅ No 404 errors
- ✅ No JavaScript errors

### Step 4: API Upload Test

**Prepare test file:**
```bash
# Use any sample .docx file (or create one)
# For this test, assume you have: sample.docx
```

**Test upload:**
```bash
curl -X POST http://localhost:3000/api/documents/analyze \
  -F "file=@sample.docx" \
  -v
```

**Expected response:**
```json
{
  "analysis": {
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "source_name": "sample.docx",
    "summary": {
      "paragraphs": 42,
      "tables": 3,
      "images": 2,
      ...
    },
    "headings": [...],
    "variables": [...],
    ...
  }
}
```

**Verify:**
- ✅ HTTP 200 status
- ✅ Valid JSON response
- ✅ `document_id` is a UUID
- ✅ `headings` array not empty (if sample has headings)

### Step 5: Generation Test

```bash
# Use document_id from previous step
DOCID="550e8400-e29b-41d4-a716-446655440000"

curl -X POST "http://localhost:3000/api/documents/$DOCID/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "clean_template",
    "variables": {},
    "cleaning_plan": null
  }' \
  -v
```

**Expected response:**
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "sample-clean.docx",
  "download_url": "/api/documents/550e8400-e29b-41d4-a716-446655440000/download",
  "summary": {
    "replaced_variables": 5,
    "cleared_paragraphs": 38,
    "removed_images": 1,
    "cleared_tables": 2
  }
}
```

### Step 6: Download Test

```bash
curl -o output.docx "http://localhost:3000/api/documents/$DOCID/download"
file output.docx
# Expected: Microsoft Word 2007+ (.docx)

# Try to open in Word/LibreOffice to verify it's valid
```

### Step 7: Logs Inspection

```bash
# Check for errors
docker compose logs backend | grep -i error
docker compose logs frontend | grep -i error

# Check health check logs
docker compose logs backend | grep health
# Should see regular health check requests (every 30s)
```

### Step 8: Stop & Cleanup

```bash
docker compose down
# Expected: Graceful shutdown of both services

# Verify volumes removed (optional, for clean slate)
docker compose down -v
docker volume ls | grep praktikit
# Should be empty
```

---

## Phase 3: Production Deployment Test

### Step 1: Production Compose

```bash
cd D:/Zcode/project7

# Create .env file for production testing
cp backend/.env.example backend/.env
# Edit if needed (LOG_LEVEL=WARNING, SESSION_TTL=3600, etc.)

# Start production stack
docker compose -f docker-compose.prod.yml up --build -d
```

**Verify:**
```bash
docker compose -f docker-compose.prod.yml ps
# Both should be "healthy"
```

### Step 2: Port Binding Check

```bash
# Frontend should only bind to localhost:8080
netstat -an | grep 8080  # Linux/Mac
# or
netstat -an | findstr 8080  # Windows

# Expected: 127.0.0.1:8080 (NOT 0.0.0.0:8080)
```

### Step 3: Same-Origin API Test

```bash
# Frontend should use relative /api paths
curl http://localhost:8080
# Check HTML source for NEXT_PUBLIC_API_URL
# Should be: process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
# But since built with NEXT_PUBLIC_API_URL="" → uses relative paths

# Test API via proxy
curl http://localhost:8080/api/docs
# Expected: Swagger UI HTML

curl http://localhost:8080/health
# Expected: {"status":"ok"}
```

### Step 4: CORS Verification

```bash
# Backend should accept requests from any origin (since it's behind proxy)
# But let's verify CORS_ORIGINS env var
docker exec praktikit-backend env | grep CORS_ORIGINS
# Expected: CORS_ORIGINS=http://localhost:3000 (or from .env)
```

### Step 5: Production Cleanup

```bash
docker compose -f docker-compose.prod.yml down -v
```

---

## Phase 4: Security & Performance Tests

### Security Checks

**1. Non-root user (optional enhancement):**
```bash
docker exec praktikit-backend whoami
# Currently: root (acceptable for MVP)
# TODO: Add USER directive to Dockerfile for hardening
```

**2. No secrets in image:**
```bash
docker history praktikit-backend:test | grep -i "password\|secret\|key"
# Should be empty
```

**3. Exposed ports:**
```bash
docker compose ps
# In dev: frontend 0.0.0.0:3000
# In prod: frontend 127.0.0.1:8080 (correct)
```

### Performance Checks

**1. Image sizes:**
```bash
docker images | grep praktikit
# backend: ~150MB (acceptable)
# frontend: ~25-30MB (excellent)
```

**2. Build time:**
```bash
time docker compose build
# Should be < 3 minutes on modern machine (first build)
# Subsequent builds: < 30 seconds (layer caching)
```

**3. Memory usage:**
```bash
docker stats --no-stream
# backend: ~100-200MB RSS (idle)
# frontend: ~5-10MB (nginx)
```

**4. Startup time:**
```bash
time docker compose up -d
docker compose logs -f
# Look for "ready for start up" (frontend) and "Uvicorn running" (backend)
# Should be < 10 seconds
```

---

## Phase 5: Integration Test (Full Flow)

### Automated Test Script

Save as `test-docker-deployment.sh`:

```bash
#!/bin/bash
set -e

echo "=== DocuTemplate Docker Deployment Test ==="

# Start services
echo "[1/7] Starting services..."
docker compose up -d --build

# Wait for health checks
echo "[2/7] Waiting for health checks..."
sleep 15
docker compose ps | grep healthy || (echo "FAIL: Services not healthy" && exit 1)

# Test health endpoint
echo "[3/7] Testing health endpoint..."
curl -f http://localhost:3000/health || (echo "FAIL: Health check failed" && exit 1)

# Test frontend
echo "[4/7] Testing frontend..."
curl -f http://localhost:3000 > /dev/null || (echo "FAIL: Frontend not accessible" && exit 1)

# Test API docs
echo "[5/7] Testing API docs..."
curl -f http://localhost:3000/api/docs > /dev/null || (echo "FAIL: API docs not accessible" && exit 1)

# Test file upload (if sample.docx exists)
if [ -f "sample.docx" ]; then
    echo "[6/7] Testing file upload..."
    RESULT=$(curl -X POST http://localhost:3000/api/documents/analyze -F "file=@sample.docx" -s)
    DOC_ID=$(echo $RESULT | grep -o '"document_id":"[^"]*"' | cut -d'"' -f4)
    echo "Document ID: $DOC_ID"
    
    echo "[7/7] Testing generation..."
    curl -X POST "http://localhost:3000/api/documents/$DOC_ID/generate" \
        -H "Content-Type: application/json" \
        -d '{"mode":"clean_template","variables":{},"cleaning_plan":null}' \
        -s | grep -q "download_url" || (echo "FAIL: Generation failed" && exit 1)
    
    echo "Downloading..."
    curl -o test-output.docx "http://localhost:3000/api/documents/$DOC_ID/download"
    [ -f test-output.docx ] || (echo "FAIL: Download failed" && exit 1)
    file test-output.docx | grep -q "Microsoft Word" || (echo "FAIL: Invalid DOCX" && exit 1)
    
    echo "✅ Full flow test PASSED"
else
    echo "[6/7] Skipping upload test (no sample.docx)"
    echo "[7/7] Skipping generation test"
fi

echo ""
echo "=== All Tests PASSED ==="
echo ""
echo "Services running at:"
echo "  Frontend: http://localhost:3000"
echo "  API docs: http://localhost:3000/api/docs"
echo ""
echo "To stop: docker compose down"
```

**Run:**
```bash
chmod +x test-docker-deployment.sh
./test-docker-deployment.sh
```

---

## Troubleshooting Common Issues

### Issue: "port already in use"

**Solution:**
```bash
# Find what's using port 3000
lsof -i :3000  # Mac/Linux
netstat -ano | findstr :3000  # Windows

# Kill the process or change port in docker-compose.yml:
# ports: - "3001:80"  # frontend on 3001 instead
```

### Issue: "frontend | wget: bad address 'backend'"

**Cause:** Backend not in same network or not started

**Solution:**
```bash
docker compose down
docker compose up --build
# Ensure backend starts first (depends_on in compose)
```

### Issue: "Backend container exits immediately"

**Check logs:**
```bash
docker compose logs backend
# Look for import errors or missing dependencies
```

**Common causes:**
- Missing dependencies in pyproject.toml
- Typo in CMD (should be `praktikit.api.app:app`)
- Port 8000 already in use inside container

### Issue: "CORS error in browser console"

**Verify CORS_ORIGINS:**
```bash
docker exec praktikit-backend env | grep CORS_ORIGINS
# Should include frontend origin
```

**Fix:**
```bash
# In backend/.env
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Restart
docker compose restart backend
```

### Issue: "413 Request Entity Too Large"

**Increase nginx limit:**
```nginx
# In frontend/nginx.conf
client_max_body_size 50M;
```

**Rebuild:**
```bash
docker compose build frontend
docker compose up -d frontend
```

---

## Success Criteria

### Must Pass
- ✅ Both containers build without errors
- ✅ Health checks pass within 30 seconds
- ✅ Frontend accessible at http://localhost:3000
- ✅ API docs accessible at /api/docs
- ✅ Can upload .docx file via API
- ✅ Can generate template
- ✅ Can download result
- ✅ Downloaded file opens in Word

### Nice to Have
- ✅ No errors in logs
- ✅ Memory usage < 300MB total
- ✅ Build time < 3 minutes
- ✅ Startup time < 15 seconds
- ✅ Image sizes reasonable (backend < 200MB, frontend < 50MB)

---

## Sign-Off Checklist

Before marking deployment as "Production Ready":

- [ ] All "Must Pass" criteria met
- [ ] Full flow test completed successfully
- [ ] No errors in logs during 5-minute idle period
- [ ] Production compose file tested (localhost binding)
- [ ] Environment variables documented and working
- [ ] Health checks functioning correctly
- [ ] CORS configured for production domains
- [ ] Tested with at least 3 different .docx files
- [ ] Downloaded templates open correctly in Word
- [ ] Leak detection works (tested with content preservation)
- [ ] Session cleanup verified (TTL expiry)

---

**After completing this checklist, update PROJECT-STATUS.md with deployment verification status.**
