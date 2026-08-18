"""Document processing API routes.

Minimal MVP API (spec Section 50):
- POST /api/documents/analyze
- POST /api/documents/{id}/generate
- GET  /api/documents/{id}/download
- DELETE /api/documents/{id}
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from praktikit.api.schemas import AnalyzeResponse, DeleteResponse, GenerateRequest, GenerateResponse
from praktikit.core.exceptions import (
    DocxValidationError,
    LeakDetectedError,
    PraktikitError,
    UnsupportedFormatError,
    ValidationFailedError,
)
from praktikit.services.docx.template_generator import TemplateGenerator
from praktikit.services.storage.session_store import get_session_store

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(file: Annotated[UploadFile, File()]) -> AnalyzeResponse:
    """Upload and analyze one DOCX file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nama file tidak tersedia.")
    if Path(file.filename).suffix.lower() != ".docx":
        # Friendly early error; validator repeats the real checks after saving.
        raise HTTPException(status_code=415, detail="Hanya file .docx yang didukung saat ini.")

    data = await file.read()
    store = get_session_store()
    session = store.create(original_filename=file.filename, source_bytes=data)

    try:
        generator = TemplateGenerator()
        analysis = generator.analyze(session.source_path)
        # Key the analysis by the session id so the frontend's analysis.document_id
        # matches the session id used for generate/download. Also surface the real
        # uploaded filename (the generator only sees the internal temp name).
        analysis.document_id = session.session_id
        analysis.source_name = session.original_filename
        store.update_analysis(session.session_id, analysis)
    except UnsupportedFormatError as exc:
        store.delete(session.session_id)
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except DocxValidationError as exc:
        store.delete(session.session_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PraktikitError as exc:
        store.delete(session.session_id)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return AnalyzeResponse(
        document_id=session.session_id,
        filename=file.filename,
        analysis=analysis,
    )


@router.post("/{document_id}/generate", response_model=GenerateResponse)
async def generate_document(document_id: str, request: GenerateRequest) -> GenerateResponse:
    """Generate a cleaned DOCX from a stored session."""
    store = get_session_store()
    session = store.get(document_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session dokumen tidak ditemukan atau sudah kedaluwarsa.")

    output_name = _safe_output_name(session.original_filename)
    output_path = session.directory / output_name
    plan = request.cleaning_plan or session.cleaning_plan

    try:
        generator = TemplateGenerator(strict_leak_check=request.strict)
        values = request.variables if request.mode == "personalized" else {}
        result = generator.generate(
            session.source_path,
            output_path,
            plan=plan,
            variable_values=values,
        )
        store.update_generated(session.session_id, result.output_path)
    except LeakDetectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PraktikitError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return GenerateResponse(
        document_id=session.session_id,
        filename=result.output_path.name,
        download_url=f"/api/documents/{session.session_id}/download",
        summary=result.summary,
    )


@router.get("/{document_id}/download")
async def download_document(document_id: str) -> FileResponse:
    """Download the generated DOCX for a session."""
    store = get_session_store()
    session = store.get(document_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session dokumen tidak ditemukan atau sudah kedaluwarsa.")
    if session.generated_path is None or not session.generated_path.exists():
        raise HTTPException(status_code=404, detail="Template belum dibuat. Jalankan generate terlebih dahulu.")
    return FileResponse(
        session.generated_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=session.generated_path.name,
    )


@router.delete("/{document_id}", response_model=DeleteResponse)
async def delete_document(document_id: str) -> DeleteResponse:
    """Delete a processing session and its temporary files."""
    deleted = get_session_store().delete(document_id)
    return DeleteResponse(document_id=document_id, deleted=deleted)


def _safe_output_name(original_filename: str) -> str:
    stem = Path(original_filename).stem or "template"
    # Keep alnum + simple separators only for the download filename.
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_", " ") else "_" for ch in stem).strip()
    clean = clean[:80] or uuid.uuid4().hex
    return f"{clean}_Template.docx"
