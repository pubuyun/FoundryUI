from __future__ import annotations

import asyncio
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

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
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

    await asyncio.gather(pump(process.stdout, "stdout", stdout_handle), pump(process.stderr, "stderr", stderr_handle))
    return_code = await process.wait()
    stdout_handle.close()
    stderr_handle.close()

    stdout_artifact = store.register_file(run_id=run_id, path=stdout_path, payload_type="Command Log", node_id=node_id, node_type=node_type, media_type="text/plain")
    stderr_artifact = store.register_file(run_id=run_id, path=stderr_path, payload_type="Command Log", node_id=node_id, node_type=node_type, media_type="text/plain")

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
