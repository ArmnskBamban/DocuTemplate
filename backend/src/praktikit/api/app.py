"""FastAPI application entry point.

Minimal MVP API server. CORS is configured for localhost development; tighten
in production. Health/root endpoints serve the future frontend's static build
(deferred to Phase 7).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from praktikit import __version__
from praktikit.api.routes import documents
from praktikit.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    configure_logging()
    yield


app = FastAPI(
    title="PraktiKit API",
    description="Smart Report Template Extractor — REST API for DOCX processing",
    version=__version__,
    lifespan=lifespan,
)

# CORS configuration (configurable via CORS_ORIGINS env var for production)
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)


@app.get("/")
async def root():
    """Root endpoint — health check / future frontend entry."""
    return {"app": "PraktiKit", "version": __version__, "status": "ok"}


@app.get("/health")
async def health():
    """Health check for load balancers."""
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled errors — never expose stack traces to users."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Terjadi kesalahan internal. Silakan coba lagi atau hubungi administrator.",
            "code": "internal_error",
        },
    )
