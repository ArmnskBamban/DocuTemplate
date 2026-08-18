"""Cleaning plan: an intermediate, reviewable list of mutations (spec Section 19).

Detection never mutates the document directly. It produces a
:class:`CleaningPlan` whose :class:`CleaningOperation` entries reference blocks
by their stable positional id. The mutation engine resolves those ids against a
clone of the source and applies exactly the listed mutations — nothing more.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class CleaningAction(StrEnum):
    KEEP = "keep"
    CLEAR_TEXT = "clear_text"  # wipe text, keep paragraph + format
    REMOVE = "remove"  # remove the element entirely
    REPLACE_WITH_PLACEHOLDER = "replace_with_placeholder"  # identity value -> {{VAR}}
    KEEP_STRUCTURE_CLEAR_CONTENT = "keep_structure_clear_content"  # heading stays, body cleared
    KEEP_TABLE_STRUCTURE = "keep_table_structure"  # keep borders/widths/header
    CLEAR_TABLE_DATA = "clear_table_data"  # empty data cells, keep header
    REMOVE_CONTENT_IMAGE = "remove_content_image"  # drop a content screenshot
    KEEP_IMAGE = "keep_image"  # logo
    REVIEW_REQUIRED = "review_required"  # default to keep, surface in UI


class CleaningOperation(BaseModel):
    """One mutation to apply to a specific block (or a cell within a table block)."""

    model_config = ConfigDict(extra="ignore")

    target: str  # block id (p-… / tbl-… / img-…)
    action: CleaningAction
    # Placeholder text for placeholder/clear-content actions.
    placeholder: str | None = None
    # When the op corresponds to a detected variable.
    variable_id: str | None = None
    # Cell coordinates (row, col) for table-cell ops.
    cell: tuple[int, int] | None = None
    confidence: float | None = None
    reason: str | None = None


class CleaningPlan(BaseModel):
    """The full, reviewable mutation list plus notes/warnings."""

    model_config = ConfigDict(extra="ignore")

    operations: list[CleaningOperation] = []
    notes: list[str] = []
    warnings: list[str] = []

    def by_target(self) -> dict[str, list[CleaningOperation]]:
        """Index operations by target block id (a block may have several ops)."""
        out: dict[str, list[CleaningOperation]] = {}
        for op in self.operations:
            out.setdefault(op.target, []).append(op)
        return out

    def action_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for op in self.operations:
            counts[op.action.value] = counts.get(op.action.value, 0) + 1
        return counts
