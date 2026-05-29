from __future__ import annotations

import asyncio
from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any

from backend.schemas.artifacts import ArtifactMetadata
from backend.schemas.errors import StructuredError
from backend.schemas.events import RunEvent, RunStatus


@dataclass
class RunRecord:
    run_id: str
    state: str = "queued"
    current_node_id: str | None = None
    current_node_type: str | None = None
    completed_nodes: int = 0
    total_nodes: int = 0
    completed_node_ids: set[str] = field(default_factory=set)
    cancel_requested: bool = False
    recent_output: deque[str] = field(default_factory=lambda: deque(maxlen=200))
    warnings: list[StructuredError] = field(default_factory=list)
    errors: list[StructuredError] = field(default_factory=list)
    artifacts: list[ArtifactMetadata] = field(default_factory=list)
    events: list[RunEvent] = field(default_factory=list)
    subscribers: list[asyncio.Queue[RunEvent]] = field(default_factory=list)
    request: Any = None
    outputs: dict[tuple[str, str], Any] = field(default_factory=dict)
    node_cache_keys: dict[str, str] = field(default_factory=dict)
    pending_inputs: dict[str, Future[dict[str, Any]]] = field(default_factory=dict)
    pending_input_requests: dict[str, RunEvent] = field(default_factory=dict)
    submitted_input_node_ids: set[str] = field(default_factory=set)

    @property
    def progress_percent(self) -> float:
        if self.total_nodes <= 0:
            return 0
        return round((self.completed_nodes / self.total_nodes) * 100, 2)


class RunRegistry:
    def __init__(self):
        self.records: dict[str, RunRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, run_id: str, total_nodes: int, request: Any = None) -> RunRecord:
        async with self._lock:
            record = RunRecord(run_id=run_id, total_nodes=total_nodes, request=request)
            self.records[run_id] = record
        await self.publish(RunEvent(event="queued", run_id=run_id, message="Run queued."))
        return record

    def get(self, run_id: str) -> RunRecord | None:
        return self.records.get(run_id)

    def status(self, run_id: str) -> RunStatus | None:
        record = self.get(run_id)
        if record is None:
            return None
        return RunStatus(
            run_id=run_id,
            state=record.state,
            current_node_id=record.current_node_id,
            current_node_type=record.current_node_type,
            completed_nodes=record.completed_nodes,
            total_nodes=record.total_nodes,
            progress_percent=record.progress_percent,
            recent_output=list(record.recent_output),
            warnings=[warning.model_dump() for warning in record.warnings],
            errors=[error.model_dump() for error in record.errors],
            pending_inputs=[
                event.model_dump(mode="json")
                for node_id, event in record.pending_input_requests.items()
                if node_id in record.pending_inputs and node_id not in record.submitted_input_node_ids
            ],
        )

    async def publish(self, event: RunEvent) -> None:
        record = self.records.get(event.run_id)
        if record is None:
            return
        event.sequence = len(record.events) + 1
        record.events.append(event)
        if event.event in {"stdout", "stderr"} and event.message:
            record.recent_output.append(f"{event.event}: {event.message}")
        if event.event == "artifact_created":
            artifact = event.data.get("artifact")
            if artifact:
                try:
                    record.artifacts.append(ArtifactMetadata.model_validate(artifact))
                except Exception:
                    pass
        for subscriber in list(record.subscribers):
            await subscriber.put(event)

    async def set_started(self, run_id: str) -> None:
        record = self.records[run_id]
        record.state = "running"
        await self.publish(RunEvent(event="started", run_id=run_id, message="Run started."))

    async def set_node_started(self, run_id: str, node_id: str, node_type: str) -> None:
        record = self.records[run_id]
        record.current_node_id = node_id
        record.current_node_type = node_type
        await self.publish(RunEvent(event="node_started", run_id=run_id, node_id=node_id, node_type=node_type))

    async def set_node_completed(self, run_id: str, node_id: str, node_type: str, cached: bool = False) -> None:
        record = self.records[run_id]
        if node_id in record.completed_node_ids:
            return
        record.completed_node_ids.add(node_id)
        if node_type != "MDNote":
            record.completed_nodes += 1
        await self.publish(
            RunEvent(
                event="node_completed",
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
                data={"completed_nodes": record.completed_nodes, "total_nodes": record.total_nodes, "cached": cached},
            )
        )

    async def add_error(self, run_id: str, error: StructuredError) -> None:
        record = self.records[run_id]
        record.errors.append(error)
        record.state = "failed"
        await self.publish(RunEvent(event="error", run_id=run_id, node_id=error.node_id, node_type=error.node_type, message=error.message, data={"error": error.model_dump()}))

    async def request_cancel(self, run_id: str) -> bool:
        record = self.records.get(run_id)
        if record is None:
            return False
        record.cancel_requested = True
        for future in record.pending_inputs.values():
            if not future.done():
                future.cancel()
        record.pending_inputs.clear()
        record.pending_input_requests.clear()
        if record.state == "queued":
            record.state = "stopped"
            await self.publish(RunEvent(event="stopped", run_id=run_id, message="Run stopped."))
        return True

    def is_cancel_requested(self, run_id: str) -> bool:
        record = self.records.get(run_id)
        return bool(record and record.cancel_requested)

    async def stop(self, run_id: str) -> None:
        record = self.records[run_id]
        for future in record.pending_inputs.values():
            if not future.done():
                future.cancel()
        record.pending_inputs.clear()
        record.pending_input_requests.clear()
        record.state = "stopped"
        record.current_node_id = None
        record.current_node_type = None
        await self.publish(RunEvent(event="stopped", run_id=run_id, message="Run stopped."))

    async def record_output(self, run_id: str, node_id: str, output_key: str, payload: Any) -> None:
        record = self.records[run_id]
        record.outputs[(node_id, output_key)] = payload

    async def record_node_cache_key(self, run_id: str, node_id: str, cache_key: str) -> None:
        record = self.records[run_id]
        record.node_cache_keys[node_id] = cache_key

    async def clear_node_cache_key(self, run_id: str, node_id: str) -> bool:
        record = self.records.get(run_id)
        if record is None:
            return False
        async with self._lock:
            return record.node_cache_keys.pop(node_id, None) is not None

    async def request_node_input(self, run_id: str, node_id: str, node_type: str, fields: list[str], payloads: dict[str, Any], defaults: dict[str, Any], choices: dict[str, list[str]] | None = None) -> dict[str, Any]:
        record = self.records[run_id]
        future: Future[dict[str, Any]] = Future()
        record.pending_inputs[node_id] = future
        record.submitted_input_node_ids.discard(node_id)
        event = RunEvent(
            event="input_required",
            run_id=run_id,
            node_id=node_id,
            node_type=node_type,
            message=f"{node_type} requires user input.",
            data={"fields": fields, "payloads": payloads, "defaults": defaults, "choices": choices or {}},
        )
        await self.publish(event)
        record.pending_input_requests[node_id] = event
        try:
            return await asyncio.wrap_future(future)
        finally:
            record.pending_inputs.pop(node_id, None)
            record.pending_input_requests.pop(node_id, None)

    async def submit_node_input(self, run_id: str, node_id: str, values: dict[str, Any]) -> bool:
        record = self.records.get(run_id)
        if record is None:
            return False
        future = record.pending_inputs.get(node_id)
        if future is None or future.done():
            return False
        record.submitted_input_node_ids.add(node_id)
        record.pending_input_requests.pop(node_id, None)
        future.set_result(values)
        await self.publish(RunEvent(event="node_progress", run_id=run_id, node_id=node_id, message="User input received."))
        return True

    async def add_warning(self, run_id: str, warning: StructuredError) -> None:
        record = self.records[run_id]
        record.warnings.append(warning)
        await self.publish(RunEvent(event="warning", run_id=run_id, node_id=warning.node_id, node_type=warning.node_type, message=warning.message, data={"warning": warning.model_dump()}))

    async def complete(self, run_id: str) -> None:
        record = self.records[run_id]
        record.state = "completed"
        record.current_node_id = None
        record.current_node_type = None
        await self.publish(RunEvent(event="completed", run_id=run_id, message="Run completed."))

    async def subscribe(self, run_id: str) -> asyncio.Queue[RunEvent] | None:
        record = self.records.get(run_id)
        if record is None:
            return None
        queue: asyncio.Queue[RunEvent] = asyncio.Queue()
        for event in record.events:
            if event.event == "input_required" and (event.node_id not in record.pending_inputs or event.node_id in record.submitted_input_node_ids):
                continue
            await queue.put(event)
        record.subscribers.append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[RunEvent]) -> None:
        record = self.records.get(run_id)
        if record and queue in record.subscribers:
            record.subscribers.remove(queue)


run_registry = RunRegistry()
