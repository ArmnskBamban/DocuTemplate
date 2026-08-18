# Quick Start with Docker

> **Docker is not installed in this environment**, but you can use these commands on any system with Docker.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/macOS) or
- [Docker Engine](https://docs.docker.com/engine/install/) (Linux)

Verify installation:

```bash
docker --version
docker compose version
```

---

## One-Command Deploy

```bash
cd D:/Zcode/project7  # or your project directory

# Build and start all services
docker compose up --build -d

# Check status
docker compose ps

# View logs
docker compose logs -f

# Access the app:
# Frontend: http://localhost:3000
# API docs: http://localhost:3000/api/docs
```

---

## Environment Configuration

1. **Copy the example config:**

```bash
cd backend
cp .env.example .env
```

2. **Edit `.env`** (optional):

```bash
LOG_LEVEL=DEBUG              # More verbose logging
MAX_UPLOAD_SIZE=52428800     # 50 MB files
SESSION_TTL=3600             # 1 hour sessions
```

3. **Restart to apply:**

```bash
docker compose down
docker compose up -d
```

---

## Stop & Remove

```bash
# Stop services (data preserved)
docker compose down

# Stop and remove volumes (temp files deleted)
docker compose down -v
```

---

## What Gets Deployed

| Service | Port | Purpose |
|---------|------|---------|
| `praktikit-frontend` | 3000 | Next.js static UI (nginx) |
| `praktikit-backend` | 8000 (internal) | FastAPI REST API |

The frontend nginx acts as a reverse proxy for `/api/*` routes to the backend.

---

## Troubleshooting

**"command not found: docker"**
- Install Docker Desktop: https://www.docker.com/products/docker-desktop/

**"port already in use"**
- Change ports in `docker-compose.yml` (frontend `3000:80` → `3001:80`)

**Container exits immediately**
```bash
docker compose logs backend
# Check for import errors or missing dependencies
```

---

## Next Steps

1. Read full deployment guide: [`DEPLOYMENT.md`](DEPLOYMENT.md)
2. Configure HTTPS: See "Behind Reverse Proxy" in DEPLOYMENT.md
3. Set up monitoring: See "Monitoring" section in DEPLOYMENT.md

---

**Need help?** Check the DEPLOYMENT.md file for detailed troubleshooting and advanced configurations.
