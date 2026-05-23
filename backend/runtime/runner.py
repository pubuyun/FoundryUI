from __future__ import annotations

import asyncio
import threading
import traceback
from queue import Queue
from typing import Callable, TypeVar

from backend.runtime.registry import run_registry
from backend.schemas.errors import BackendError, make_error
from backend.schemas.workflow import RunCreateRequest
from backend.workflow.ryvencore_adapter import execute_ryvencore_workflow
from backend.workflow.validation import validate_workflow

T = TypeVar("T")


async def run_workflow(run_id: str, request: RunCreateRequest) -> None:
    graph = request.workflow_graph()
    errors = validate_workflow(graph)
    if errors:
        for error in errors:
            error.run_id = run_id
            await run_registry.add_error(run_id, error)
        return

    try:
        await run_registry.set_started(run_id)
        await _run_blocking_in_thread(lambda: execute_ryvencore_workflow(run_id=run_id, request=request))
        await run_registry.complete(run_id)
    except BackendError as exc:
        exc.error.run_id = exc.error.run_id or run_id
        await run_registry.add_error(run_id, exc.error)
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        await run_registry.add_error(
            run_id,
            make_error(
                "UNHANDLED_RUNTIME_ERROR",
                str(exc),
                run_id=run_id,
                details={"traceback": traceback.format_exc()},
            ),
        )


async def _run_blocking_in_thread(fn: Callable[[], T]) -> T:
    results: Queue[tuple[bool, T | BaseException]] = Queue(maxsize=1)

    def target() -> None:
        try:
            results.put((True, fn()))
        except BaseException as exc:
            results.put((False, exc))

    thread = threading.Thread(target=target, name="foundryui-ryvencore-runner", daemon=True)
    thread.start()
    while thread.is_alive():
        await asyncio.sleep(0.05)
    ok, value = results.get()
    if ok:
        return value  # type: ignore[return-value]
    raise value
