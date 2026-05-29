from __future__ import annotations

import asyncio
import json
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from backend.artifacts.archive import create_run_archive
from backend.artifacts.registry import artifact_store
from backend.bio.fasta import parse_fasta
from backend.bio.pdb import validate_pdb
from backend.runtime.events import sse_encode
from backend.runtime.queue import QueuedRun, run_queue
from backend.runtime.registry import run_registry
from backend.runtime.runner import run_workflow
from backend.runtime.sessions import session_store
from backend.runtime.uploads import upload_store
from backend.schemas.artifacts import ArtifactList
from backend.schemas.errors import make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import EmbeddedUpload, FoundryWorkflowDocument, RunCreateRequest, WorkflowGraph, WorkflowValidationResponse
from backend.workflow.validation import validate_workflow
from backend.nodes.common import option_file_tokens
from backend.workflow.frontend_catalog import frontend_node_catalog
from backend.nodes.registry import node_for


app = FastAPI(title="FoundryUI Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
_worker_task: asyncio.Task | None = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
async def api_health() -> dict[str, str]:
    return await health()


@app.get("/api/nodes")
async def node_catalog() -> dict[str, Any]:
    return frontend_node_catalog()


def _ensure_worker() -> None:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())


def _executable_node_count(graph: WorkflowGraph) -> int:
    return sum(1 for node in graph.nodes if node.type != "MDNote")


async def _worker_loop() -> None:
    while True:
        queued = await run_queue.get()
        try:
            await run_workflow(queued.run_id, queued.request)
        finally:
            run_queue.task_done()


@app.post("/api/uploads")
async def upload_files(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    files: list[EmbeddedUpload] = []

    if "multipart/form-data" in content_type:
        form = await request.form()
        for _, value in form.multi_items():
            if hasattr(value, "filename"):
                raw = await value.read()
                files.append(EmbeddedUpload(name=value.filename, type=_detect_type(value.filename), content=raw.decode(errors="replace")))
    else:
        body = await request.json()
        if isinstance(body, dict) and "files" in body:
            files = [EmbeddedUpload.model_validate(item) for item in body["files"]]
        elif isinstance(body, dict) and {"name", "content"} <= set(body):
            files = [EmbeddedUpload.model_validate(body)]

    if not files:
        raise HTTPException(status_code=400, detail="No upload files were provided.")

    response_files = []
    for item in files:
        file_type = (item.type or _detect_type(item.name)).lower()
        _validate_upload(file_type, item.content)
        stored = upload_store.save(name=item.name, content=item.content, file_type=file_type)
        response_files.append({"file_id": stored.file_id, "name": stored.name, "type": stored.type, "size": stored.path.stat().st_size})
    return {"files": response_files}


@app.post("/api/workflows/validate", response_model=WorkflowValidationResponse)
async def validate_workflow_endpoint(payload: dict[str, Any]) -> WorkflowValidationResponse:
    graph = _graph_from_payload(payload)
    errors = validate_workflow(graph)
    return WorkflowValidationResponse(
        valid=not errors,
        errors=[error.model_dump() for error in errors],
        node_count=len(graph.nodes),
        connection_count=len(graph.connections),
    )


@app.post("/api/runs")
async def create_run(request: RunCreateRequest) -> dict[str, Any]:
    try:
        graph = request.workflow_graph()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    errors = [*validate_workflow(graph), *_validate_run_uploads(request)]
    if errors:
        return {
            "accepted": False,
            "errors": [error.model_dump() for error in errors],
        }

    session = session_store.get(request.session_id) if request.session_id else None
    previous_run_id = session.latest_run_id if session else None
    if previous_run_id:
        request = request.model_copy(update={"previous_run_id": previous_run_id})
    run_id = f"run_{uuid.uuid4().hex}"
    artifact_store.init_run(run_id)
    await run_registry.create(run_id, total_nodes=_executable_node_count(graph), request=request)
    if request.session_id:
        session_store.update(request.session_id, latest_run_id=run_id, document=request.document.model_dump(mode="json") if request.document else None)
    _ensure_worker()
    await run_queue.put(QueuedRun(run_id=run_id, request=request))
    return {"accepted": True, "run_id": run_id, "state": "queued"}


@app.post("/api/runs/{run_id}/stop")
async def stop_run(run_id: str):
    if not await run_registry.request_cancel(run_id):
        raise HTTPException(status_code=404, detail="Run not found.")
    return {"accepted": True, "run_id": run_id, "state": "stopping"}


@app.post("/api/runs/{run_id}/input")
async def submit_run_input(run_id: str, payload: dict[str, Any]):
    node_id = str(payload.get("node_id") or "")
    values = payload.get("values") or {}
    if not node_id or not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="node_id and values are required.")
    if not await run_registry.submit_node_input(run_id, node_id, values):
        raise HTTPException(status_code=404, detail="No pending input request for this node.")
    return {"accepted": True, "run_id": run_id, "node_id": node_id}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    status = run_registry.status(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return status


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str):
    queue = await run_registry.subscribe(run_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Run not found.")

    async def generate():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield sse_encode(event)
                    if event.event in {"completed", "error", "stopped"}:
                        break
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            run_registry.unsubscribe(run_id, queue)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/runs/{run_id}/artifacts", response_model=ArtifactList)
async def list_artifacts(run_id: str) -> ArtifactList:
    if run_registry.get(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return ArtifactList(run_id=run_id, artifacts=artifact_store.list_run(run_id))


@app.get("/api/runs/{run_id}/outputs")
async def list_outputs(run_id: str) -> dict[str, Any]:
    record = run_registry.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    outputs = []
    for (node_id, output_key), payload in record.outputs.items():
        typed = TypedPayload.model_validate(payload)
        outputs.append(
            {
                "node_id": node_id,
                "output_key": output_key,
                "type_name": typed.type_name,
                "item_count": typed.item_count,
                "artifact_ids": typed.artifact_ids,
                "paths": typed.paths,
            }
        )
    return {"run_id": run_id, "outputs": outputs}


@app.get("/api/runs/{run_id}/outputs/{node_id}/{output_key}/download")
async def download_output(run_id: str, node_id: str, output_key: str):
    record = run_registry.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    payload = record.outputs.get((node_id, output_key))
    if payload is None:
        raise HTTPException(status_code=404, detail="Output not found.")
    typed = TypedPayload.model_validate(payload)
    if not typed.paths:
        raise HTTPException(status_code=404, detail="Output has no files.")
    should_zip = len(typed.paths) > 1 or typed.type_name.startswith("Batch ")
    if not should_zip:
        path = artifact_store.absolute(run_id, typed.paths[0])
        return FileResponse(path, filename=Path(typed.paths[0]).name)
    archive_dir = artifact_store.run_dir(run_id) / "output_archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{node_id}_{output_key}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel_path in typed.paths:
            path = artifact_store.absolute(run_id, rel_path)
            if path.is_file():
                archive.write(path, Path(rel_path).name)
    return FileResponse(archive_path, media_type="application/zip", filename=archive_path.name)


@app.get("/api/runs/{run_id}/saves", response_model=ArtifactList)
async def list_saved_artifacts(run_id: str) -> ArtifactList:
    if run_registry.get(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    artifacts = [artifact for artifact in artifact_store.list_run(run_id) if artifact.path.startswith("saves/") and artifact.media_type == "application/zip"]
    return ArtifactList(run_id=run_id, artifacts=artifacts)


@app.post("/api/sessions")
async def create_session(payload: dict[str, Any] | None = None):
    record = session_store.create(document=(payload or {}).get("document"))
    return record.__dict__


@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": [record.__dict__ for record in session_store.list()]}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    record = session_store.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return record.__dict__


@app.put("/api/sessions/{session_id}")
async def update_session(session_id: str, payload: dict[str, Any]):
    record = session_store.update(session_id, latest_run_id=payload.get("latest_run_id"), document=payload.get("document"))
    return record.__dict__


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    if not session_store.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"deleted": True}


@app.get("/api/artifacts/{artifact_id}")
async def download_artifact(artifact_id: str):
    artifact = artifact_store.artifacts.get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    path = artifact_store.absolute(artifact.run_id, artifact.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found.")
    return FileResponse(path, media_type=artifact.media_type, filename=Path(artifact.path).name)


@app.get("/api/runs/{run_id}/archive")
async def download_archive(run_id: str):
    if run_registry.get(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    archive = create_run_archive(artifact_store, run_id)
    return FileResponse(archive, media_type="application/zip", filename=f"{run_id}.zip")


def _graph_from_payload(payload: dict[str, Any]) -> WorkflowGraph:
    if "workflow" in payload and payload.get("fileType") == "FoundryUIWorkflow":
        return FoundryWorkflowDocument.model_validate(payload).workflow
    if "document" in payload:
        return FoundryWorkflowDocument.model_validate(payload["document"]).workflow
    if "workflow" in payload:
        return WorkflowGraph.model_validate(payload["workflow"])
    return WorkflowGraph.model_validate(payload)


def _detect_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdb":
        return "pdb"
    if suffix in {".fasta", ".fa"}:
        return "fasta"
    return "unknown"


def _validate_upload(file_type: str, content: str) -> None:
    try:
        if file_type == "pdb":
            validate_pdb(content)
        elif file_type in {"fasta", "fa"}:
            parse_fasta(content)
        else:
            raise ValueError("Unsupported upload type.")
    except ValueError as exc:
        error = make_error("INVALID_UPLOAD", str(exc), details={"file_type": file_type})
        raise HTTPException(status_code=400, detail=error.model_dump()) from exc


def _validate_run_uploads(request: RunCreateRequest):
    errors = []
    graph = request.workflow_graph()
    uploads = request.embedded_uploads()
    for node in graph.nodes:
        node_definition = node_for(node.type)
        upload_validation = node_definition.upload_validation if node_definition is not None else None
        if upload_validation is None:
            continue
        node_errors = _validate_input_node_files(
            node,
            uploads,
            upload_validation.allowed_types,
            upload_validation.missing_message,
            upload_validation.missing_code,
            upload_validation.invalid_code,
        )
        if node_errors:
            errors.extend(node_errors)
    return errors


def _validate_input_node_files(node, uploads: dict[str, list[EmbeddedUpload]], allowed_types: set[str], missing_message: str, missing_code: str, invalid_code: str):
    errors = []
    refs = option_file_tokens(node)
    embedded = _embedded_uploads_for_node(node, uploads, refs)
    if not embedded and not refs:
        return [make_error(missing_code, missing_message, node_id=node.id, node_type=node.type, option_key="file")]
    for item in embedded:
        file_type = (item.type or _detect_type(item.name)).lower()
        if file_type not in allowed_types:
            errors.append(make_error(invalid_code, f"{node.type} received an invalid uploaded file type.", node_id=node.id, node_type=node.type, option_key="file", details={"file": item.name, "file_type": file_type, "allowed_types": sorted(allowed_types)}))
            continue
        try:
            _validate_upload_content_for_run(file_type, item.content)
        except ValueError as exc:
            errors.append(make_error(invalid_code, str(exc), node_id=node.id, node_type=node.type, option_key="file", details={"file": item.name, "file_type": file_type}))
    for ref in refs:
        stored = upload_store.get(ref)
        if stored is None and any(item.name == ref for item in embedded):
            continue
        if stored is None:
            errors.append(make_error(missing_code, f"{node.type} references an unknown uploaded file id.", node_id=node.id, node_type=node.type, option_key="file", details={"file_id": ref}))
            continue
        if stored.type not in allowed_types:
            errors.append(make_error(invalid_code, f"{node.type} references an invalid uploaded file type.", node_id=node.id, node_type=node.type, option_key="file", details={"file_id": ref, "file": stored.name, "file_type": stored.type, "allowed_types": sorted(allowed_types)}))
            continue
        try:
            _validate_upload_content_for_run(stored.type, stored.path.read_text())
        except ValueError as exc:
            errors.append(make_error(invalid_code, str(exc), node_id=node.id, node_type=node.type, option_key="file", details={"file_id": ref, "file": stored.name, "file_type": stored.type}))
    return errors


def _embedded_uploads_for_node(node, uploads: dict[str, list[EmbeddedUpload]], refs: list[str]) -> list[EmbeddedUpload]:
    embedded = uploads.get(node.id) or []
    if embedded:
        return embedded
    file_names = set(refs)
    if not file_names:
        return []
    return [item for items in uploads.values() for item in items if item.name in file_names]


def _validate_upload_content_for_run(file_type: str, content: str) -> None:
    if file_type == "pdb":
        validate_pdb(content)
    elif file_type in {"fasta", "fa"}:
        parse_fasta(content)
    else:
        raise ValueError("Unsupported upload type.")
