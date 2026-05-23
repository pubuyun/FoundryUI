from __future__ import annotations

import json

from backend.schemas.events import RunEvent


def sse_encode(event: RunEvent) -> str:
    return f"event: {event.event}\ndata: {json.dumps(event.model_dump(mode='json'))}\n\n"
