"""Test suite configuration."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_dir():
    """Temporary directory for test outputs."""
    with tempfile.TemporaryDirectory(prefix="praktikit_test_") as td:
        yield Path(td)


@pytest.fixture
def acceptance_docx(tmp_dir):
    """Fixture matching the spec's acceptance scenario (Section 74)."""
    from tests.fixtures.builders import build_acceptance_docx

    path = tmp_dir / "acceptance.docx"
    return build_acceptance_docx(path)


@pytest.fixture
def custom_heading_docx(tmp_dir):
    """Fixture with I./A./B. style headings."""
    from tests.fixtures.builders import build_custom_heading_docx

    path = tmp_dir / "custom_heading.docx"
    return build_custom_heading_docx(path)


@pytest.fixture
def table_docx(tmp_dir):
    """Fixture with identity + data tables."""
    from tests.fixtures.builders import build_table_docx

    path = tmp_dir / "table.docx"
    return build_table_docx(path)
