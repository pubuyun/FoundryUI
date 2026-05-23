from __future__ import annotations

import asyncio
from dataclasses import dataclass

from backend.schemas.workflow import RunCreateRequest


@dataclass
class QueuedRun:
    run_id: str
    request: RunCreateRequest


run_queue: asyncio.Queue[QueuedRun] = asyncio.Queue()
