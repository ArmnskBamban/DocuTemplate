"""Detected identity variables (spec Section 17/18).

A variable is an identity field (Nama, NIM, Kelas, …) whose value should be
replaced with a placeholder. ``original_value`` is personal data: it lives in
the in-memory model and the user-facing review, but it must NEVER be written to
server logs or sent to an external/AI provider (spec Section 11/47/68).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class VariableField(BaseModel):
    """A detected identity field to be replaced with a placeholder."""

    model_config = ConfigDict(extra="ignore")

    id: str  # v-000001
    block_id: str  # paragraph or table block id
    label: str  # "Nama", "NIM", …
    original_value: str  # personal data — never log/externalise
    placeholder: str  # "{{NAMA}}" or "{{FIELD_1}}"
    standard: bool  # matched a known identity field
    location: str  # "inline" | "stacked" | "table"
    # For table variables: cell coordinates (row, col) of the value cell.
    cell: tuple[int, int] | None = None

    def safe_view(self) -> dict:
        """A dict with the original value redacted — safe for logs/debugging."""
        return {
            "id": self.id,
            "label": self.label,
            "placeholder": self.placeholder,
            "standard": self.standard,
            "location": self.location,
            "block_id": self.block_id,
            "value_present": bool(self.original_value),
        }
