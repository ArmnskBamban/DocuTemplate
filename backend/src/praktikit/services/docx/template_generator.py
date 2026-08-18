"""Template generator (spec Section 41).

Orchestrates the full pipeline: validate → clone → parse → detect structure →
classify → detect variables → build cleaning plan → mutate → validate → leak
check. The original source file is **never** modified.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from praktikit.core.exceptions import GenerationError, LeakDetectedError, ValidationFailedError
from praktikit.core.logging import get_logger
from praktikit.models.analysis import AnalysisResult
from praktikit.models.cleaning import CleaningPlan
from praktikit.services.docx.cleaning_planner import CleaningPlanner
from praktikit.services.docx.leak_detector import LeakDetector
from praktikit.services.docx.mutation_engine import MutationEngine
from praktikit.services.docx.parser import DocxParser
from praktikit.services.docx.semantic_classifier import HeuristicSemanticClassifier
from praktikit.services.docx.structure_detector import StructureDetector
from praktikit.services.docx.validator import validate_docx_file
from praktikit.services.docx.variable_detector import VariableDetector

logger = get_logger(__name__)


class GenerationResult:
    """Result of generating a template."""

    def __init__(
        self,
        output_path: Path,
        analysis: AnalysisResult,
        plan: CleaningPlan,
        summary: dict,
    ):
        self.output_path = output_path
        self.analysis = analysis
        self.plan = plan
        self.summary = summary  # {replaced_variables, cleared_paragraphs, removed_images, cleared_tables}


class TemplateGenerator:
    """Run the end-to-end pipeline from a source DOCX to a clean template."""

    def __init__(
        self,
        strict_leak_check: bool | None = None,
        leak_threshold: float | None = None,
    ):
        from praktikit.core.config import get_settings

        settings = get_settings()
        self.strict_leak_check = (
            settings.strict_leak_check if strict_leak_check is None else strict_leak_check
        )
        self.leak_threshold = (
            settings.leak_similarity_threshold if leak_threshold is None else leak_threshold
        )

    def analyze(self, source: str | Path) -> AnalysisResult:
        """Validate + parse + detect structure/classifications/variables.

        Returns an :class:`AnalysisResult` (no document is mutated).
        """
        path = validate_docx_file(source)
        parse = DocxParser.from_path(path).parse()
        blocks, styles = parse.blocks, parse.styles_by_id
        meta = parse.document_meta

        detector = StructureDetector(blocks, styles)
        detection = detector.detect()

        classifier = HeuristicSemanticClassifier()
        classifications = classifier.classify_all(
            blocks, detection.heading_info, detection.structure_tree, detection.cover_end_index
        )

        var_detector = VariableDetector()
        variables = var_detector.detect(blocks, classifications, detection.cover_end_index)

        from praktikit.models.analysis import AnalysisSummary

        summary = AnalysisSummary.from_analysis(
            blocks, detection.heading_info, variables, meta.section_count
        )

        result = AnalysisResult(
            source_name=Path(path).name,
            document_meta=meta,
            summary=summary,
            blocks=blocks,
            structure=detection.structure_tree,
            headings=detection.heading_info,
            classifications=classifications,
            variables=variables,
        )

        # Build a default cleaning plan (user can override in a UI later).
        planner = CleaningPlanner()
        plan = planner.build(
            blocks,
            detection.heading_info,
            classifications,
            variables,
            detection.cover_end_index,
        )
        result.cleaning_plan = plan
        result.uncertain_elements = list(plan.warnings)
        return result

    def generate(
        self,
        source: str | Path,
        output_path: str | Path,
        plan: CleaningPlan | None = None,
        variable_values: dict[str, str] | None = None,
    ) -> GenerationResult:
        """Clone the source, apply the plan, validate, and leak-check.

        ``plan`` defaults to the auto-built plan from :meth:`analyze`.
        ``variable_values`` maps placeholder (e.g. ``{{NAMA}}``) → replacement
        (personalized mode); ``None``/empty keeps placeholders as-is.
        """
        path = validate_docx_file(source)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        analysis = self.analyze(path)
        if plan is None:
            plan = analysis.cleaning_plan
            if plan is None:
                raise GenerationError("Cleaning plan kosong — tidak ada operasi yang dihasilkan.")

        # Apply variable values (personalized mode): replace placeholders in plan.
        resolved_plan = self._resolve_variables(plan, variable_values or {})

        engine = MutationEngine(path)
        working = engine.apply(resolved_plan)

        # Copy working file to the requested output path.
        shutil.copy2(working, out)

        # Validate the generated output.
        from praktikit.services.docx.validator import validate_docx_file as validate_output

        try:
            validate_output(out)
        except Exception as exc:
            raise ValidationFailedError(f"Output gagal validasi: {exc}") from exc

        # Leak detection: compare source body content vs output.
        leak_detector = LeakDetector(threshold=self.leak_threshold)
        leaks = leak_detector.detect(path, out, analysis)
        if leaks and self.strict_leak_check:
            raise LeakDetectedError(
                f"Potential old content detected ({len(leaks)} item(s)). "
                "Strict leak check enabled — generation refused. Review the cleaning plan."
            )

        summary = self._build_summary(analysis, resolved_plan)
        return GenerationResult(output_path=out, analysis=analysis, plan=resolved_plan, summary=summary)

    def _resolve_variables(self, plan: CleaningPlan, values: dict[str, str]) -> CleaningPlan:
        """Substitute variable values into placeholder ops (personalized mode).

        Keys are normalized so both ``"NAMA"`` and ``"{{NAMA}}"`` work.
        """
        if not values:
            return plan
        normalized: dict[str, str] = {}
        for key, value in values.items():
            name = str(key).strip().strip("{}").strip()
            if name:
                normalized[f"{{{{{name}}}}}"] = value
        ops = []
        for op in plan.operations:
            if op.placeholder and op.placeholder in normalized:
                op = op.model_copy(update={"placeholder": normalized[op.placeholder]})
            ops.append(op)
        return plan.model_copy(update={"operations": ops})

    def _build_summary(self, analysis: AnalysisResult, plan: CleaningPlan) -> dict:
        counts = plan.action_counts()
        return {
            "replaced_variables": counts.get("replace_with_placeholder", 0),
            "cleared_paragraphs": counts.get("keep_structure_clear_content", 0),
            "removed_images": counts.get("remove_content_image", 0),
            "cleared_tables": counts.get("clear_table_data", 0),
            "total_operations": len(plan.operations),
        }
