from __future__ import annotations

import zipfile
from pathlib import Path

from backend.artifacts.store import ArtifactStore


def create_run_archive(store: ArtifactStore, run_id: str) -> Path:
    root = store.run_dir(run_id)
    archive_path = root / "archive.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in root.rglob("*"):
            if path.is_file() and path != archive_path:
                archive.write(path, path.relative_to(root).as_posix())
    return archive_path
