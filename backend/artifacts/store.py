from __future__ import annotations

import csv
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from backend.schemas.artifacts import ArtifactMetadata


class ArtifactStore:
    def __init__(self, base_dir: Path | str = Path(__file__).resolve().parents[1] / "runs"):
        self.base_dir = Path(base_dir)
        self.artifacts: dict[str, ArtifactMetadata] = {}

    def run_dir(self, run_id: str) -> Path:
        return self.base_dir / run_id

    def init_run(self, run_id: str) -> Path:
        root = self.run_dir(run_id)
        self.artifacts = {artifact_id: artifact for artifact_id, artifact in self.artifacts.items() if artifact.run_id != run_id}
        for child in ("uploads", "nodes", "saves", "logs"):
            (root / child).mkdir(parents=True, exist_ok=True)
        self.write_manifest(run_id)
        return root

    def node_dir(self, run_id: str, node_id: str, node_type: str) -> Path:
        safe_type = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in node_type)
        safe_node_id = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in node_id)
        path = self.run_dir(run_id) / "nodes" / f"{safe_node_id}_{safe_type}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def relative(self, run_id: str, path: Path) -> str:
        return path.relative_to(self.run_dir(run_id)).as_posix()

    def absolute(self, run_id: str, run_relative_path: str) -> Path:
        path = (self.run_dir(run_id) / run_relative_path).resolve()
        root = self.run_dir(run_id).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Artifact path escapes the run directory.")
        return path

    def register_file(
        self,
        *,
        run_id: str,
        path: Path,
        payload_type: str,
        node_id: str | None = None,
        node_type: str | None = None,
        media_type: str = "application/octet-stream",
        item_count: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactMetadata:
        artifact_id = f"artifact_{uuid.uuid4().hex}"
        rel_path = self.relative(run_id, path)
        artifact = ArtifactMetadata(
            artifact_id=artifact_id,
            run_id=run_id,
            node_id=node_id,
            node_type=node_type,
            payload_type=payload_type,
            media_type=media_type,
            path=rel_path,
            byte_size=path.stat().st_size if path.exists() else 0,
            item_count=item_count,
            metadata=metadata or {},
        )
        self.artifacts[artifact_id] = artifact
        self.write_manifest(run_id)
        return artifact

    def write_text(
        self,
        *,
        run_id: str,
        path: Path,
        content: str,
        payload_type: str,
        node_id: str | None = None,
        node_type: str | None = None,
        media_type: str = "text/plain",
        item_count: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactMetadata:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return self.register_file(
            run_id=run_id,
            path=path,
            payload_type=payload_type,
            node_id=node_id,
            node_type=node_type,
            media_type=media_type,
            item_count=item_count,
            metadata=metadata,
        )

    def write_json(self, *, run_id: str, path: Path, data: Any, payload_type: str, node_id: str | None = None, node_type: str | None = None, item_count: int = 1) -> ArtifactMetadata:
        return self.write_text(
            run_id=run_id,
            path=path,
            content=json.dumps(data, indent=2),
            payload_type=payload_type,
            node_id=node_id,
            node_type=node_type,
            media_type="application/json",
            item_count=item_count,
        )

    def write_csv(self, *, run_id: str, path: Path, rows: list[dict[str, Any]], payload_type: str, node_id: str | None = None, node_type: str | None = None) -> ArtifactMetadata:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames: list[str] = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames or ["value"])
            writer.writeheader()
            writer.writerows(rows)
        return self.register_file(
            run_id=run_id,
            path=path,
            payload_type=payload_type,
            node_id=node_id,
            node_type=node_type,
            media_type="text/csv",
            item_count=len(rows),
        )

    def copy_artifact(self, *, run_id: str, source_relative_path: str, destination: Path, payload_type: str, node_id: str | None, node_type: str | None) -> ArtifactMetadata:
        source = self.absolute(run_id, source_relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return self.register_file(run_id=run_id, path=destination, payload_type=payload_type, node_id=node_id, node_type=node_type)

    def list_run(self, run_id: str) -> list[ArtifactMetadata]:
        return [artifact for artifact in self.artifacts.values() if artifact.run_id == run_id]

    def write_manifest(self, run_id: str) -> None:
        root = self.run_dir(run_id)
        root.mkdir(parents=True, exist_ok=True)
        data = [artifact.model_dump(mode="json") for artifact in self.list_run(run_id)]
        (root / "manifest.json").write_text(json.dumps({"run_id": run_id, "artifacts": data}, indent=2))
