"""Top-level analysis result (spec Section 32).

Ties together the parsed blocks, document metadata, detected structure,
classifications, headings and variables. This is what the CLI/API return and
what the cleaning planner consumes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from praktikit.models.blocks import DocumentBlock, ParagraphBlock, TableBlock
from praktikit.models.classification import Classification
from praktikit.models.cleaning import CleaningPlan
from praktikit.models.document import DocumentMeta
from praktikit.models.structure import HeadingInfo, StructureNode
from praktikit.models.variables import VariableField


class AnalysisSummary(BaseModel):
    """Headline counts shown in the analysis screen (spec Section 35)."""

    model_config = ConfigDict(extra="ignore")

    paragraphs: int = 0
    tables: int = 0
    images: int = 0
    sections: int = 0
    major_headings: int = 0
    subheadings: int = 0
    variables: int = 0

    @classmethod
    def from_analysis(
        cls,
        blocks: list[DocumentBlock],
        headings: list[HeadingInfo],
        variables: list[VariableField],
        section_count: int,
    ) -> AnalysisSummary:
        paragraphs = sum(1 for b in blocks if isinstance(b, ParagraphBlock))
        tables = sum(1 for b in blocks if isinstance(b, TableBlock))
        images = sum(len(getattr(b, "images", [])) for b in blocks)
        major = sum(1 for h in headings if h.level == 0)
        sub = sum(1 for h in headings if h.level > 0)
        return cls(
            paragraphs=paragraphs,
            tables=tables,
            images=images,
            sections=section_count,
            major_headings=major,
            subheadings=sub,
            variables=len(variables),
        )


class AnalysisResult(BaseModel):
    """The complete output of analyzing one document."""

    model_config = ConfigDict(extra="ignore")

    document_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    source_name: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    document_meta: DocumentMeta
    summary: AnalysisSummary
    blocks: list[DocumentBlock] = []
    structure: list[StructureNode] = []
    headings: list[HeadingInfo] = []
    classifications: dict[str, Classification] = {}
    variables: list[VariableField] = []
    cleaning_plan: CleaningPlan | None = None
    warnings: list[str] = []
    uncertain_elements: list[str] = []  # block ids needing review

    def to_debug_dict(self) -> dict:
        """A JSON-safe view for ``--debug``: blocks/fingerprints/scores/decisions.

        Identity values are redacted (debug dumps may be shared to improve
        detectors — no personal data leaves the user's machine).
        """
        data = self.model_dump(mode="json")
        # Redact variable original values.
        for var in data.get("variables", []):
            var["original_value"] = "<redacted>"
        return data
