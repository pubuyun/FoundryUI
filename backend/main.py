from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from backend.artifacts.archive import create_run_archive
from backend.artifacts.registry import artifact_store
from backend.bio.fasta import parse_fasta
from backend.bio.ligand import validate_sdf, smiles_to_pdb
from backend.bio.pdb import validate_pdb
from backend.runtime.events import sse_encode
from backend.runtime.queue import QueuedRun, run_queue
from backend.runtime.registry import run_registry
from backend.runtime.runner import run_workflow
from backend.runtime.uploads import upload_store
from backend.schemas.artifacts import ArtifactList
from backend.schemas.errors import make_error
from backend.schemas.workflow import EmbeddedUpload, FoundryWorkflowDocument, RunCreateRequest, WorkflowGraph, WorkflowValidationResponse
from backend.workflow.validation import validate_workflow


app = FastAPI(title="FoundryUI Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_worker_task: asyncio.Task | None = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _ensure_worker() -> None:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())


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

    run_id = f"run_{uuid.uuid4().hex}"
    artifact_store.init_run(run_id)
    await run_registry.create(run_id, total_nodes=len(graph.nodes), request=request)
    _ensure_worker()
    await run_queue.put(QueuedRun(run_id=run_id, request=request))
    return {"accepted": True, "run_id": run_id, "state": "queued"}


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
                    if event.event in {"completed", "error"}:
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
    if suffix == ".sdf":
        return "sdf"
    if suffix in {".fasta", ".fa"}:
        return "fasta"
    return "unknown"


def _validate_upload(file_type: str, content: str) -> None:
    try:
        if file_type == "pdb":
            validate_pdb(content)
        elif file_type == "sdf":
            validate_sdf(content)
        elif file_type in {"fasta", "fa"}:
            parse_fasta(content)
        elif file_type == "smiles":
            smiles_to_pdb(content.strip())
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
        if node.type == "LigandInput":
            source = str(node.options.get("source", "SMILES")).upper()
            if source == "SMILES":
                if not str(node.options.get("smiles", "")).strip():
                    errors.append(make_error("MISSING_LIGAND_SMILES", "LigandInput requires SMILES text.", node_id=node.id, node_type=node.type, option_key="smiles"))
            elif not uploads.get(node.id) and not _has_stored_file_refs(str(node.options.get("file", ""))):
                errors.append(make_error("MISSING_LIGAND_FILE", "LigandInput requires uploaded PDB/SDF content or upload file ids.", node_id=node.id, node_type=node.type, option_key="file"))
        elif node.type == "ProteinInput":
            if not uploads.get(node.id) and not _has_stored_file_refs(str(node.options.get("file", ""))):
                errors.append(make_error("MISSING_PROTEIN_FILE", "ProteinInput requires uploaded PDB content or upload file ids.", node_id=node.id, node_type=node.type, option_key="file"))
        elif node.type == "SequenceInput":
            if not uploads.get(node.id) and not _has_stored_file_refs(str(node.options.get("file", ""))):
                errors.append(make_error("MISSING_FASTA_FILE", "SequenceInput requires uploaded FASTA content or upload file ids.", node_id=node.id, node_type=node.type, option_key="file"))
    return errors


def _has_stored_file_refs(value: str) -> bool:
    refs = [part.strip() for part in value.split(",") if part.strip()]
    return bool(refs) and all(upload_store.get(ref) is not None for ref in refs)
