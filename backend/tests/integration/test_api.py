"""API integration tests (spec Section 50)."""

from pathlib import Path

from fastapi.testclient import TestClient

from praktikit.api.app import app
from praktikit.services.storage.session_store import reset_session_store

client = TestClient(app)


def _upload(acceptance_docx: Path) -> str:
    """Upload a fixture and return the document_id."""
    with open(acceptance_docx, "rb") as fh:
        resp = client.post(
            "/api/documents/analyze",
            files={"file": ("report.docx", fh, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["document_id"]
    assert data["analysis"]["summary"]["major_headings"] >= 4
    return data["document_id"]


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_analyze_generate_download_flow(acceptance_docx, tmp_dir):
    """Full API flow: analyze → generate → download."""
    # Clean store between tests.
    reset_session_store(None)
    doc_id = _upload(acceptance_docx)

    resp = client.post(f"/api/documents/{doc_id}/generate", json={"mode": "clean_template"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["summary"]["replaced_variables"] >= 2
    assert data["download_url"].endswith("/download")

    dl = client.get(data["download_url"])
    assert dl.status_code == 200
    assert dl.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert len(dl.content) > 0


def test_generate_personalized(acceptance_docx, tmp_dir):
    """Personalized mode substitutes variable values."""
    reset_session_store(None)
    doc_id = _upload(acceptance_docx)

    resp = client.post(
        f"/api/documents/{doc_id}/generate",
        json={"mode": "personalized", "variables": {"NAMA": "Jiyad", "NIM": "24109999"}},
    )
    assert resp.status_code == 200, resp.text
    dl = client.get(resp.json()["download_url"])
    # DOCX bodies are zipped — reopen with python-docx to inspect actual text.
    from io import BytesIO

    from docx import Document

    doc = Document(BytesIO(dl.content))
    joined = "\n".join(p.text for p in doc.paragraphs)
    assert "Jiyad" in joined
    assert "24109999" in joined
    assert "{{NAMA}}" not in joined
    assert "John Doe" not in joined


def test_analyze_rejects_non_docx(tmp_dir):
    """Uploading a non-docx file returns 415."""
    fake = tmp_dir / "fake.pdf"
    fake.write_bytes(b"%PDF-1.4")
    with open(fake, "rb") as fh:
        resp = client.post("/api/documents/analyze", files={"file": ("x.pdf", fh, "application/pdf")})
    assert resp.status_code == 415


def test_generate_unknown_session():
    """Unknown session returns 404."""
    resp = client.post("/api/documents/does-not-exist/generate", json={})
    assert resp.status_code == 404


def test_download_before_generate(acceptance_docx):
    """Download before generate returns 404."""
    reset_session_store(None)
    doc_id = _upload(acceptance_docx)
    resp = client.get(f"/api/documents/{doc_id}/download")
    assert resp.status_code == 404


def test_delete_session(acceptance_docx):
    """Delete removes the session."""
    reset_session_store(None)
    doc_id = _upload(acceptance_docx)
    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    # Subsequent generate fails.
    resp = client.post(f"/api/documents/{doc_id}/generate", json={})
    assert resp.status_code == 404
