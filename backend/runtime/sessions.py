from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SessionRecord:
    session_id: str
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    latest_run_id: str | None = None
    document: dict[str, Any] | None = None


class SessionStore:
    def __init__(self, root: Path | str = Path(__file__).resolve().parents[1] / "sessions"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, document: dict[str, Any] | None = None) -> SessionRecord:
        record = SessionRecord(session_id=f"session_{uuid.uuid4().hex}", document=document)
        self.save(record)
        return record

    def get(self, session_id: str) -> SessionRecord | None:
        path = self._path(session_id)
        if not path.is_file():
            return None
        data = json.loads(path.read_text())
        return SessionRecord(**data)

    def list(self) -> list[SessionRecord]:
        records = [SessionRecord(**json.loads(path.read_text())) for path in self.root.glob("session_*.json")]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def update(self, session_id: str, *, latest_run_id: str | None = None, document: dict[str, Any] | None = None) -> SessionRecord:
        record = self.get(session_id) or SessionRecord(session_id=session_id)
        if latest_run_id is not None:
            record.latest_run_id = latest_run_id
        if document is not None:
            record.document = document
        record.updated_at = _now()
        self.save(record)
        return record

    def delete(self, session_id: str) -> bool:
        path = self._path(session_id)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def save(self, record: SessionRecord) -> None:
        self._path(record.session_id).write_text(json.dumps(record.__dict__, indent=2))

    def _path(self, session_id: str) -> Path:
        safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in session_id)
        return self.root / f"{safe}.json"


session_store = SessionStore()
