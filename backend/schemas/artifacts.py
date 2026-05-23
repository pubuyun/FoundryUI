from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ArtifactMetadata(BaseModel):
    artifact_id: str
    run_id: str
    node_id: str | None = None
    node_type: str | None = None
    payload_type: str
    media_type: str = "application/octet-stream"
    path: str
    byte_size: int = 0
    item_count: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = {}


class ArtifactList(BaseModel):
    run_id: str
    artifacts: list[ArtifactMetadata]
