"""PraktiKit CLI (spec Section 49).

Commands:

- ``praktikit analyze <file>`` — print detected structure summary.
- ``praktikit clean <file> --output out.docx`` — generate a clean template.
- ``praktikit analyze <file> --json out.json --debug debug.json`` — machine output.
- ``praktikit serve`` — run the FastAPI development server.

The CLI exercises the exact same core engine the REST API will expose, so it
doubles as the development/test harness.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from praktikit import __version__
from praktikit.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@click.group()
@click.version_option(__version__, prog_name="praktikit")
def main() -> None:
    """PraktiKit — Smart Report Template Extractor."""


@main.command("analyze")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json", "json_out", type=click.Path(path_type=Path), default=None,
              help="Write the full analysis result as JSON.")
@click.option("--debug", type=click.Path(path_type=Path), default=None,
              help="Write a redacted debug dump (blocks/scores/decisions).")
def analyze_cmd(file: Path, json_out: Path | None, debug: Path | None) -> None:
    """Analyze a DOCX report and print its detected structure."""
    configure_logging()
    from praktikit.services.docx.template_generator import TemplateGenerator

    try:
        generator = TemplateGenerator()
        result = generator.analyze(file)
    except Exception as exc:  # noqa: BLE001 - CLI must print friendly errors
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"\n📄 {result.source_name}")
    click.echo("  " + "─" * 46)
    s = result.summary
    click.echo(
        f"  {s.major_headings} BAB · {s.subheadings} subbagian · "
        f"{s.tables} tabel · {s.images} gambar · {s.variables} variable"
    )
    click.echo(f"  Paper: {result.document_meta.page_layout.size_name or 'custom'} "
               f"({result.document_meta.page_layout.orientation.value})")
    click.echo(f"  Margins (cm): {result.document_meta.margins.to_cm()}")

    _print_structure(result)
    click.echo()

    if result.variables:
        click.echo("Variable terdeteksi:")
        for v in result.variables:
            marker = "" if v.standard else " (baru)"
            click.echo(f"  • {v.label}: {v.original_value!r} → {v.placeholder}{marker}")
        click.echo()

    if result.warnings or result.uncertain_elements:
        click.echo("⚠ Perlu review:")
        for w in (result.warnings or result.uncertain_elements)[:10]:
            click.echo(f"  • {w}")
        click.echo()

    if json_out is not None:
        json_out.write_text(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
        click.echo(f"Analysis JSON → {json_out}")
    if debug is not None:
        debug.write_text(json.dumps(result.to_debug_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        click.echo(f"Debug dump → {debug}")


@main.command("clean")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None,
              help="Output .docx path (default: <name>_Template.docx next to the input).")
@click.option("--strict/--no-strict", default=None,
              help="Fail on detected old-content leaks (default: config STRICT_LEAK_CHECK).")
@click.option("--var", "vars", multiple=True, type=(str, str),
              help="Personalized mode: replace placeholder with value, e.g. --var NAMA Jiyad.")
@click.option("--json", "json_out", type=click.Path(path_type=Path), default=None,
              help="Write the analysis result as JSON.")
def clean_cmd(
    file: Path, output: Path | None, strict: bool | None, vars: list[tuple[str, str]], json_out: Path | None
) -> None:
    """Generate a clean reusable template from a DOCX report."""
    configure_logging()
    from praktikit.services.docx.template_generator import TemplateGenerator

    if output is None:
        output = file.with_name(f"{file.stem}_Template.docx")

    values = {k: v for k, v in vars}
    try:
        generator = TemplateGenerator(strict_leak_check=strict)
        result = generator.generate(file, output, variable_values=values)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if json_out is not None:
        json_out.write_text(json.dumps(result.analysis.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")

    click.echo(f"\n✅ Template berhasil dibuat → {result.output_path}")
    click.echo("  " + "─" * 40)
    sum_ = result.summary
    click.echo(f"  ✓ {sum_['replaced_variables']} variable diganti")
    click.echo(f"  ✓ {sum_['cleared_paragraphs']} paragraf lama dibersihkan")
    click.echo(f"  ✓ {sum_['removed_images']} gambar lama dihapus")
    click.echo(f"  ✓ {sum_['cleared_tables']} tabel dibersihkan")
    click.echo("  ✓ Struktur/format dipertahankan")
    if values:
        click.echo(f"  ✓ Nilai personal diterapkan: {len(values)} placeholder")
    click.echo()


def _print_structure(result) -> None:
    """Render the structure tree as indented text."""
    click.echo()
    click.echo("Detected structure:")
    for node in result.structure:
        click.echo(f"  {_node_label(node)}")
        for child in node.children[:8]:
            click.echo(f"    └ {_node_label(child)}")


def _node_label(node) -> str:
    num = f"{node.number} " if node.number else ""
    return f"{num}{node.title}" if node.title else node.node_type


@main.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host.")
@click.option("--port", default=8000, show_default=True, help="Bind port.")
@click.option("--reload", is_flag=True, help="Auto-reload on code changes (dev).")
def serve_cmd(host: str, port: int, reload: bool) -> None:
    """Start the PraktiKit REST API (FastAPI/uvicorn)."""
    from praktikit.api.serve import serve

    click.echo(f"PraktiKit API → http://{host}:{port}  (docs: /docs)")
    serve(host=host, port=port, reload=reload)
