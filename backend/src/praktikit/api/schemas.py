"""API request/response schemas.

The API layer deliberately mirrors the core engine's Pydantic models but keeps
HTTP/session concerns separate from DOCX processing concerns.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from praktikit.models.analysis import AnalysisResult
from praktikit.models.cleaning import CleaningPlan


class ApiError(BaseModel):
    """User-facing error payload."""

    detail: str
    code: str = "error"


class AnalyzeResponse(BaseModel):
    """Response from POST /api/documents/analyze."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    filename: str
    analysis: AnalysisResult


class GenerateRequest(BaseModel):
    """Request body for POST /api/documents/{id}/generate."""

    model_config = ConfigDict(extra="ignore")

    mode: str = Field(default="clean_template", pattern="^(clean_template|personalized)$")
    cleaning_plan: CleaningPlan | None = None
    # Values keyed by either placeholder name ("NAMA") or full placeholder ("{{NAMA}}").
    variables: dict[str, str] = {}
    strict: bool | None = None


class GenerateResponse(BaseModel):
    """Response after generating a document."""

    model_config = ConfigDict(extra="ignore")

    document_id: str
    filename: str
    download_url: str
    summary: dict


class DeleteResponse(BaseModel):
    """Response after deleting a processing session."""

    document_id: str
    deleted: bool
