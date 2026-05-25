from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path

from backend.artifacts.store import ArtifactStore
from backend.runtime.registry import RunRegistry
from backend.schemas.errors import BackendError, make_error
from backend.schemas.events import RunEvent


async def run_command_streaming(
    *,
    command: list[str],
    cwd: Path,
    run_id: str,
    node_id: str,
    node_type: str,
    registry: RunRegistry,
    store: ArtifactStore,
) -> None:
    logs_dir = store.run_dir(run_id) / "logs"
    stdout_path = logs_dir / f"{node_id}_{node_type}.stdout.log"
    stderr_path = logs_dir / f"{node_id}_{node_type}.stderr.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_handle = stdout_path.open("w")
    stderr_handle = stderr_path.open("w")
    process: asyncio.subprocess.Process | None = None

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        last_stderr = ""

        async def pump(stream: asyncio.StreamReader | None, event_name: str, handle) -> None:
            nonlocal last_stderr
            if stream is None:
                return
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip()
                handle.write(text + "\n")
                handle.flush()
                if event_name == "stderr" and text:
                    last_stderr = text
                await registry.publish(RunEvent(event=event_name, run_id=run_id, node_id=node_id, node_type=node_type, message=text))

        pump_tasks = [asyncio.create_task(pump(process.stdout, "stdout", stdout_handle)), asyncio.create_task(pump(process.stderr, "stderr", stderr_handle))]
        while process.returncode is None:
            if registry.is_cancel_requested(run_id):
                await _terminate_process_group(process, registry, run_id, node_id, node_type)
                await asyncio.gather(*pump_tasks, return_exceptions=True)
                stdout_artifact, stderr_artifact = _register_logs(store, run_id, stdout_path, stderr_path, node_id, node_type)
                raise BackendError(
                    make_error(
                        "RUN_CANCELLED",
                        "Run was stopped by the user and the external command process group was terminated.",
                        run_id=run_id,
                        node_id=node_id,
                        node_type=node_type,
                        recoverable=True,
                        details={"command": command, "stdout_artifact_id": stdout_artifact.artifact_id, "stderr_artifact_id": stderr_artifact.artifact_id},
                        log_artifact_id=stderr_artifact.artifact_id,
                    )
                )
            await asyncio.sleep(0.2)
        await asyncio.gather(*pump_tasks)
        return_code = await process.wait()

        stdout_artifact, stderr_artifact = _register_logs(store, run_id, stdout_path, stderr_path, node_id, node_type)

        if return_code != 0:
            message = f"Command failed with exit code {return_code}."
            if last_stderr:
                message = f"{message} Last stderr: {last_stderr}"
            raise BackendError(
                make_error(
                    "SUBPROCESS_FAILED",
                    message,
                    run_id=run_id,
                    node_id=node_id,
                    node_type=node_type,
                    details={"command": command, "return_code": return_code, "stdout_artifact_id": stdout_artifact.artifact_id},
                    log_artifact_id=stderr_artifact.artifact_id,
                )
            )
    except asyncio.CancelledError:
        if process is not None and process.returncode is None:
            await _terminate_process_group(process, registry, run_id, node_id, node_type)
        raise
    finally:
        stdout_handle.close()
        stderr_handle.close()


async def _terminate_process_group(process: asyncio.subprocess.Process, registry: RunRegistry, run_id: str, node_id: str, node_type: str) -> None:
    await registry.publish(RunEvent(event="warning", run_id=run_id, node_id=node_id, node_type=node_type, message="Stopping external command process group."))
    _signal_process_group(process, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        await registry.publish(RunEvent(event="warning", run_id=run_id, node_id=node_id, node_type=node_type, message="External command did not stop; force killing process group."))
        _signal_process_group(process, signal.SIGKILL)
        await process.wait()


def _signal_process_group(process: asyncio.subprocess.Process, sig: signal.Signals) -> None:
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        return


def _register_logs(store: ArtifactStore, run_id: str, stdout_path: Path, stderr_path: Path, node_id: str, node_type: str):
    stdout_artifact = store.register_file(run_id=run_id, path=stdout_path, payload_type="Command Log", node_id=node_id, node_type=node_type, media_type="text/plain")
    stderr_artifact = store.register_file(run_id=run_id, path=stderr_path, payload_type="Command Log", node_id=node_id, node_type=node_type, media_type="text/plain")
    return stdout_artifact, stderr_artifact
