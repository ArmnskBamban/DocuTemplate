"""Cleaning plan builder (spec Section 19/48).

Transforms analysis results (classifications, variables, headings) into a
reviewable :class:`CleaningPlan` — a list of mutations to apply to the DOCX
clone. No document is modified during planning; the plan is decoupled from
execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from praktikit.models.classification import Classification, SemanticRole
from praktikit.models.cleaning import CleaningAction, CleaningOperation, CleaningPlan
from praktikit.models.structure import HeadingInfo
from praktikit.models.variables import VariableField
from praktikit.services.docx.placeholder import placeholder_for_heading

if TYPE_CHECKING:
    from praktikit.models.blocks import DocumentBlock


class CleaningPlanner:
    """Produce a CleaningPlan from analysis artifacts."""

    def build(
        self,
        blocks: list[DocumentBlock],
        headings: list[HeadingInfo],
        classifications: dict[str, Classification],
        variables: list[VariableField],
        cover_end_index: int,
    ) -> CleaningPlan:
        ops: list[CleaningOperation] = []
        notes: list[str] = []
        warnings: list[str] = []
        var_by_block: dict[str, VariableField] = {v.block_id: v for v in variables if v.location != "table"}
        heading_context = self._build_heading_context(blocks, headings)

        # One default operation per block.
        for block in blocks:
            clf = classifications.get(block.id)
            if clf is None:
                ops.append(CleaningOperation(target=block.id, action=CleaningAction.KEEP, reason="unclassified"))
                continue

            # Inline/stacked variables override the semantic action for that paragraph.
            if block.id in var_by_block:
                var = var_by_block[block.id]
                ops.append(
                    CleaningOperation(
                        target=block.id,
                        action=CleaningAction.REPLACE_WITH_PLACEHOLDER,
                        placeholder=var.placeholder,
                        variable_id=var.id,
                        confidence=0.90,
                        reason=f"variable:{var.label}",
                    )
                )
                continue

            action, placeholder = self._decide_action(block, clf, heading_context)
            if action == CleaningAction.REVIEW_REQUIRED:
                warnings.append(f"Uncertain: {block.id} ({clf.role.value}, conf={clf.confidence:.2f})")
            ops.append(
                CleaningOperation(
                    target=block.id,
                    action=action,
                    placeholder=placeholder,
                    confidence=clf.confidence,
                    reason=clf.role.value,
                )
            )

        # Table variables replace individual value cells (supplement the table-level op).
        for var in variables:
            if var.location == "table" and var.cell is not None:
                ops.append(
                    CleaningOperation(
                        target=var.block_id,
                        action=CleaningAction.REPLACE_WITH_PLACEHOLDER,
                        placeholder=var.placeholder,
                        variable_id=var.id,
                        cell=var.cell,
                        confidence=0.90,
                        reason=f"variable:{var.label}",
                    )
                )

        return CleaningPlan(operations=ops, notes=notes, warnings=warnings)

    def _decide_action(
        self, block, clf: Classification, heading_context: dict[str, str]
    ) -> tuple[CleaningAction, str | None]:
        role = clf.role
        auto = clf.automation

        if role in (
            SemanticRole.COVER_STATIC,
            SemanticRole.REFERENCES_HEADING,
            SemanticRole.APPENDIX_HEADING,
            SemanticRole.CAPTION,
            SemanticRole.PAGE_BREAK,
            SemanticRole.BLANK,
        ):
            return CleaningAction.KEEP, None

        if role == SemanticRole.IMAGE_LOGO:
            return CleaningAction.KEEP_IMAGE, None

        if role == SemanticRole.IMAGE_CONTENT:
            # Keep the image in the template — a template preserves the figure's
            # position/size so the next user pastes their own result there. The
            # previous report's specific *text* is cleared elsewhere; the image
            # itself stays. (REMOVE_CONTENT_IMAGE remains available as an option
            # but is no longer the default behaviour.)
            return CleaningAction.KEEP_IMAGE, None

        if role in (
            SemanticRole.CHAPTER_HEADING,
            SemanticRole.SECTION_HEADING,
            SemanticRole.SUBSECTION_HEADING,
        ):
            return CleaningAction.KEEP, None

        if role == SemanticRole.INSTRUCTION_TEXT:
            # Remove list items (a), b), c), etc.) entirely from template.
            return CleaningAction.REMOVE, None

        if role == SemanticRole.COVER_VARIABLE:
            return CleaningAction.REVIEW_REQUIRED, None

        if role == SemanticRole.TABLE_IDENTITY:
            return CleaningAction.KEEP_TABLE_STRUCTURE, None

        if role in (SemanticRole.TABLE_CONTENT, SemanticRole.TABLE_TEMPLATE):
            # Remove content tables entirely from template so users can add their own.
            # Only identity tables (Nama|John) are kept with placeholders.
            return CleaningAction.REMOVE, None

        if role == SemanticRole.BODY_CONTENT:
            ph = heading_context.get(block.id, "[Isi di sini]")
            if auto.value in ("auto", "review"):
                return CleaningAction.KEEP_STRUCTURE_CLEAR_CONTENT, ph
            return CleaningAction.REVIEW_REQUIRED, ph

        # Unknown: preserve + flag.
        return CleaningAction.KEEP, None

    def _build_heading_context(self, blocks: list, headings: list[HeadingInfo]) -> dict[str, str]:
        """Map each non-heading block id to a placeholder from the nearest preceding heading."""
        heading_titles = {h.block_id: h.title for h in headings}
        result: dict[str, str] = {}
        last_title: str | None = None
        for block in blocks:
            if block.id in heading_titles:
                last_title = heading_titles[block.id]
            elif last_title is not None:
                result[block.id] = placeholder_for_heading(last_title)
        return result
