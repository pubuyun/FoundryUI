from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredUpload:
    file_id: str
    name: str
    type: str
    path: Path


class UploadStore:
    def __init__(self, base_dir: Path | str = Path(__file__).resolve().parents[1] / "uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_dir / "index.json"
        self._index: dict[str, dict] = {}
        if self.index_path.exists():
            self._index = json.loads(self.index_path.read_text())

    def save(self, *, name: str, content: str, file_type: str) -> StoredUpload:
        file_id = f"upload_{uuid.uuid4().hex}"
        suffix = Path(name).suffix or f".{file_type}"
        path = self.base_dir / f"{file_id}{suffix}"
        path.write_text(content)
        stored = StoredUpload(file_id=file_id, name=name, type=file_type, path=path)
        self._index[file_id] = {"file_id": file_id, "name": name, "type": file_type, "path": str(path)}
        self._write_index()
        return stored

    def get(self, file_id: str) -> StoredUpload | None:
        item = self._index.get(file_id)
        if not item:
            return None
        return StoredUpload(file_id=item["file_id"], name=item["name"], type=item["type"], path=Path(item["path"]))

    def _write_index(self) -> None:
        self.index_path.write_text(json.dumps(self._index, indent=2))


upload_store = UploadStore()
