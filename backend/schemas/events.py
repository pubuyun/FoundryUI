from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


EventType = Literal[
    "queued",
    "started",
    "node_started",
    "node_progress",
    "stdout",
    "stderr",
    "node_completed",
    "artifact_created",
    "warning",
    "error",
    "completed",
    "stopped",
]


class RunEvent(BaseModel):
    event: EventType
    run_id: str
    sequence: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    node_id: str | None = None
    node_type: str | None = None
    message: str | None = None
    data: dict[str, Any] = {}


class RunStatus(BaseModel):
    run_id: str
    state: str
    current_node_id: str | None = None
    current_node_type: str | None = None
    completed_nodes: int = 0
    total_nodes: int = 0
    progress_percent: float = 0
    recent_output: list[str] = []
    warnings: list[Any] = []
    errors: list[Any] = []
