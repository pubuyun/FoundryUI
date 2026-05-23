from __future__ import annotations

import os
from pathlib import Path


def executable(env_key: str, default: str) -> str:
    return os.environ.get(env_key, default)


def checkpoint_path(env_key: str, default_relative_path: str) -> Path:
    configured = os.environ.get(env_key)
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path(__file__).resolve().parents[2] / default_relative_path).resolve()


def collect_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)
