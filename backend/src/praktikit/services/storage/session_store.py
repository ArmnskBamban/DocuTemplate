"""Temporary processing session store (spec Section 51).

MVP uses isolated temporary directories and in-memory session metadata — no
database. Sessions are lazy-expired and can be explicitly deleted. Original
documents are never stored permanently.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from praktikit.core.config import get_settings
from praktikit.models.analysis import AnalysisResult
from praktikit.models.cleaning import CleaningPlan


@dataclass
class ProcessingSession:
    """Temporary document-processing session."""

    session_id: str
    original_filename: str
    directory: Path
    source_path: Path
    analysis_result: AnalysisResult | None = None
    cleaning_plan: CleaningPlan | None = None
    generated_path: Path | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)


class SessionStore:
    """In-memory session registry with temp-dir cleanup."""

    def __init__(self, ttl_seconds: int | None = None, base_dir: Path | None = None):
        settings = get_settings()
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.session_ttl
        configured_base = settings.temp_base()
        self.base_dir = base_dir or configured_base or Path(tempfile.gettempdir())
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, ProcessingSession] = {}

    def create(self, original_filename: str, source_bytes: bytes) -> ProcessingSession:
        """Create an isolated temp directory and persist uploaded bytes safely."""
        self.cleanup_expired()
        sid = uuid.uuid4().hex
        directory = Path(tempfile.mkdtemp(prefix=f"praktikit_{sid}_", dir=str(self.base_dir)))
        # Always use a random internal filename; never trust the user filename as a path.
        source_path = directory / f"source_{uuid.uuid4().hex}.docx"
        source_path.write_bytes(source_bytes)
        session = ProcessingSession(
            session_id=sid,
            original_filename=original_filename,
            directory=directory,
            source_path=source_path,
        )
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> ProcessingSession | None:
        """Return a session or None when missing/expired."""
        self.cleanup_expired()
        session = self._sessions.get(session_id)
        if session is not None:
            session.touch()
        return session

    def update_analysis(self, session_id: str, analysis: AnalysisResult) -> None:
        session = self._sessions[session_id]
        session.analysis_result = analysis
        session.cleaning_plan = analysis.cleaning_plan
        session.touch()

    def update_generated(self, session_id: str, generated_path: Path) -> None:
        session = self._sessions[session_id]
        session.generated_path = generated_path
        session.touch()

    def delete(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        shutil.rmtree(session.directory, ignore_errors=True)
        return True

    def cleanup_expired(self) -> int:
        """Delete expired sessions; returns number removed."""
        now = datetime.now(UTC)
        expired: list[str] = []
        ttl = timedelta(seconds=self.ttl_seconds)
        for sid, session in self._sessions.items():
            if now - session.updated_at > ttl:
                expired.append(sid)
        for sid in expired:
            self.delete(sid)
        return len(expired)


_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Return the process-wide session store."""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


def reset_session_store(store: SessionStore | None = None) -> None:
    """Replace/reset the global store (tests)."""
    global _store
    _store = store
