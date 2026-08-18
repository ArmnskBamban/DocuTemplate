# DocuTemplate Deployment Guide

> **Last updated:** 2026-08-12
> **Target environments:** Docker, Docker Compose, bare metal

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Docker Compose)](#quick-start-docker-compose)
3. [Production Deployment](#production-deployment)
4. [Environment Variables](#environment-variables)
5. [Health Checks](#health-checks)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### For Docker Deployment

- Docker 20.10+ and Docker Compose 2.0+
- At least 1GB RAM available
- 2GB disk space (for images and temp files)

### For Bare Metal Deployment

- Python 3.11+
- uv package manager (`pip install uv`)
- Node.js 20+ and npm (for frontend)
- nginx (for serving static frontend + reverse proxy)

---

## Quick Start (Docker Compose)

### 1. Clone and Configure

```bash
cd D:/Zcode/project7  # or your project directory
cp backend/.env.example backend/.env
```

### 2. Build and Run

```bash
docker-compose up --build
```

This will:
- Build the backend (FastAPI on port 8000, internal only)
- Build the frontend (Next.js static export served by nginx on port 3000)
- Set up networking and volumes

### 3. Access the Application

- **Frontend:** http://localhost:3000
- **Backend API docs:** http://localhost:3000/api/docs (proxied via nginx)
- **Health check:** http://localhost:3000/health

### 4. Stop

```bash
docker-compose down
```

To remove volumes (temp files):

```bash
docker-compose down -v
```

---

## Production Deployment

### Architecture

```
           ┌──────────────┐
Internet ──┤  nginx/LB    ├─── HTTPS termination
           └──────────────┘
                  │
                  ▼
        ┌──────────────────┐
        │  praktikit-      │
        │  frontend        │      Static files + /api proxy
        │  (nginx:alpine)  │
        └──────────────────┘
                  │ /api/*
                  ▼
        ┌──────────────────┐
        │  praktikit-      │
        │  backend         │      FastAPI (uvicorn)
        │  (python:3.11)   │
        └──────────────────┘
```

### Option 1: Docker Compose with Environment File

Create a production `.env` file:

```bash
# .env (root directory)
NEXT_PUBLIC_API_URL=
CORS_ORIGINS=https://praktikit.example.com
MAX_UPLOAD_SIZE=26214400
SESSION_TTL=3600
LOG_LEVEL=WARNING
STRICT_LEAK_CHECK=true
```

Run with:

```bash
docker-compose --env-file .env up -d
```

### Option 2: Behind Reverse Proxy (Recommended)

If you have an external nginx/Caddy/Traefik handling HTTPS:

1. **Expose only the frontend container:**

```yaml
# docker-compose.prod.yml
version: "3.9"

services:
  backend:
    build: ./backend
    container_name: praktikit-backend
    restart: unless-stopped
    env_file: ./backend/.env
    volumes:
      - praktikit-temp:/tmp/praktikit
    networks:
      - praktikit-network
    # No ports exposed to host

  frontend:
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_API_URL: ""  # Same-origin
    container_name: praktikit-frontend
    restart: unless-stopped
    ports:
      - "127.0.0.1:8080:80"  # Only bind to localhost
    depends_on:
      - backend
    networks:
      - praktikit-network

networks:
  praktikit-network:
    driver: bridge

volumes:
  praktikit-temp:
```

2. **Configure your external reverse proxy:**

Example nginx config:

```nginx
upstream praktikit {
    server 127.0.0.1:8080;
}

server {
    listen 443 ssl http2;
    server_name praktikit.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    client_max_body_size 30M;  # Allow uploads

    location / {
        proxy_pass http://praktikit;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Option 3: Split Backend/Frontend Domains

If backend and frontend are on different domains (e.g., `api.praktikit.com` and `praktikit.com`):

1. **Build frontend with explicit API URL:**

```bash
docker build --build-arg NEXT_PUBLIC_API_URL=https://api.praktikit.com ./frontend
```

2. **Update backend CORS:**

```bash
# backend/.env
CORS_ORIGINS=https://praktikit.com,https://www.praktikit.com
```

---

## Environment Variables

### Backend (backend/.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE` | 26214400 | Max file size in bytes (25 MB) |
| `SESSION_TTL` | 1800 | Session expiry in seconds (30 min) |
| `TEMP_DIRECTORY` | `/tmp/praktikit` | Base directory for temp files |
| `AUTO_THRESHOLD` | 0.90 | Confidence for automatic handling |
| `REVIEW_THRESHOLD` | 0.70 | Confidence for auto+review |
| `STRICT_LEAK_CHECK` | true | Fail if old content detected |
| `LEAK_SIMILARITY_THRESHOLD` | 0.6 | Shingle overlap ratio (0.0-1.0) |
| `AI_ENABLED` | false | Enable LLM classifier (not implemented) |
| `LOG_LEVEL` | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |

### Frontend (build-time)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Backend API URL (baked at build) |

**Important:** When using same-origin deployment (nginx proxy), set `NEXT_PUBLIC_API_URL=""` (empty string) so API calls use relative paths.

---

## Health Checks

Both containers have built-in health checks:

### Backend Health

```bash
curl http://localhost:3000/health
# or internal: docker exec praktikit-backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
```

Expected response:

```json
{"status": "ok"}
```

### Frontend Health

```bash
curl http://localhost:3000
```

Expected: HTTP 200 with HTML content.

### Docker Health Status

```bash
docker ps
```

Look for `(healthy)` in the STATUS column.

---

## Monitoring

### Logs

**View all logs:**

```bash
docker-compose logs -f
```

**Backend only:**

```bash
docker-compose logs -f backend
```

**Frontend only:**

```bash
docker-compose logs -f frontend
```

### Metrics

Recommended additions for production (not included in base setup):

1. **Prometheus + Grafana:** Add `prometheus-fastapi-instrumentator` to backend, expose `/metrics`.
2. **Sentry:** Set `SENTRY_DSN` in backend/.env for error tracking.
3. **Log aggregation:** Ship logs to ELK/Loki stack via Docker logging driver.

---

## Troubleshooting

### Frontend shows "Failed to fetch" or CORS errors

**Cause:** CORS mismatch or incorrect `NEXT_PUBLIC_API_URL`.

**Fix:**

1. Check backend CORS_ORIGINS includes the frontend origin:
   ```bash
   docker exec praktikit-backend env | grep CORS_ORIGINS
   ```

2. For same-origin deployment, ensure `NEXT_PUBLIC_API_URL=""` during build and nginx proxy is configured.

3. Rebuild frontend if `NEXT_PUBLIC_API_URL` changed:
   ```bash
   docker-compose build frontend
   docker-compose up -d frontend
   ```

### Backend container exits immediately

**Cause:** Missing dependencies or misconfiguration.

**Fix:**

1. Check logs:
   ```bash
   docker-compose logs backend
   ```

2. Verify Python imports:
   ```bash
   docker-compose run --rm backend python -c "from praktikit.api.app import app; print(app)"
   ```

3. Ensure pyproject.toml is correctly copied (check Dockerfile COPY steps).

### File upload fails with 413 Request Entity Too Large

**Cause:** nginx client_max_body_size limit.

**Fix:**

Add to `frontend/nginx.conf`:

```nginx
client_max_body_size 30M;
```

Or set in external reverse proxy config.

### Temp files filling disk

**Cause:** Sessions not expiring or TTL too long.

**Fix:**

1. Lower `SESSION_TTL` in backend/.env (e.g., 1800 = 30 min).
2. Manually clean volume:
   ```bash
   docker-compose down
   docker volume rm project7_praktikit-temp
   docker-compose up -d
   ```

3. Set up cron job to clean old temp files (outside container):
   ```bash
   find /var/lib/docker/volumes/project7_praktikit-temp/_data -type d -mtime +1 -exec rm -rf {} +
   ```

### Health check failing

**Cause:** App not starting or port mismatch.

**Fix:**

1. Check if app is listening:
   ```bash
   docker exec praktikit-backend netstat -tlnp | grep 8000
   ```

2. Test health endpoint manually:
   ```bash
   docker exec praktikit-backend curl -f http://localhost:8000/health
   ```

3. Check startup logs for errors:
   ```bash
   docker-compose logs backend | grep ERROR
   ```

---

## Security Hardening (Production Checklist)

- [ ] Use HTTPS (TLS 1.2+) with valid certificates
- [ ] Set `STRICT_LEAK_CHECK=true` (default)
- [ ] Restrict CORS_ORIGINS to known domains only
- [ ] Run containers as non-root user (add `USER` directive to Dockerfiles)
- [ ] Enable Docker content trust: `export DOCKER_CONTENT_TRUST=1`
- [ ] Use secrets management (Docker secrets, Vault) instead of .env files for sensitive data
- [ ] Set up rate limiting on reverse proxy (e.g., nginx `limit_req_zone`)
- [ ] Enable firewall rules (only expose port 443)
- [ ] Regular security updates: `docker-compose pull && docker-compose up -d`
- [ ] Monitor logs for suspicious activity (400/500 errors, large file attempts)

---

## Scaling

### Horizontal Scaling (Multiple Backend Instances)

Update `docker-compose.yml`:

```yaml
services:
  backend:
    # ... existing config ...
    deploy:
      replicas: 3  # Run 3 backend instances

  frontend:
    # ... existing config ...
```

**Note:** Current session store is in-memory (not shared). For true horizontal scaling:

1. Implement sticky sessions (nginx `ip_hash`), OR
2. Move session store to Redis/PostgreSQL (Phase 4 roadmap)

### Resource Limits

Add to `docker-compose.yml`:

```yaml
services:
  backend:
    # ... existing config ...
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

---

## Bare Metal Deployment (Alternative)

### Backend

```bash
cd backend
uv sync
export $(cat .env | xargs)
uv run uvicorn praktikit.api.app:app --host 0.0.0.0 --port 8000 --workers 4
```

Or use systemd service (create `/etc/systemd/system/praktikit-backend.service`).

### Frontend

```bash
cd frontend
export NEXT_PUBLIC_API_URL=http://localhost:8000
npm ci
npm run build
# Serve out/ directory with nginx (config similar to frontend/nginx.conf)
```

---

## Next Steps

- [ ] Set up CI/CD pipeline (GitHub Actions, GitLab CI)
- [ ] Add monitoring (Prometheus + Grafana)
- [ ] Implement database for saved templates (Phase 4)
- [ ] Add automated E2E tests (Playwright)
- [ ] Set up staging environment

---

**Questions?** Refer to `handoff.md` for architecture details or open an issue.
