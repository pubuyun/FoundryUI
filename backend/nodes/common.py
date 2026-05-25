from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.artifacts.store import ArtifactStore
from backend.runtime.registry import RunRegistry
from backend.runtime.uploads import upload_store
from backend.schemas.artifacts import ArtifactMetadata
from backend.schemas.events import RunEvent
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import EmbeddedUpload, WorkflowNode


@dataclass
class ExecutionContext:
    run_id: str
    store: ArtifactStore
    registry: RunRegistry
    uploads: dict[str, list[EmbeddedUpload]]
    ligand_counter: int = 0

    def next_ligand_residue_name(self) -> str:
        self.ligand_counter += 1
        if self.ligand_counter > 9:
            raise ValueError("Only nine auto-renamed single ligands are supported because PDB residue names are three characters.")
        return f"L:{self.ligand_counter}"

    async def artifact_created(self, artifact: ArtifactMetadata) -> None:
        await self.registry.publish(
            RunEvent(
                event="artifact_created",
                run_id=self.run_id,
                node_id=artifact.node_id,
                node_type=artifact.node_type,
                data={"artifact": artifact.model_dump(mode="json")},
            )
        )

    async def write_text_artifact(self, node: WorkflowNode, path: Path, content: str, payload_type: str, media_type: str = "text/plain", item_count: int = 1) -> ArtifactMetadata:
        artifact = self.store.write_text(
            run_id=self.run_id,
            path=path,
            content=content,
            payload_type=payload_type,
            node_id=node.id,
            node_type=node.type,
            media_type=media_type,
            item_count=item_count,
        )
        await self.artifact_created(artifact)
        return artifact

    async def write_json_artifact(self, node: WorkflowNode, path: Path, data: Any, payload_type: str, item_count: int = 1) -> ArtifactMetadata:
        artifact = self.store.write_json(run_id=self.run_id, path=path, data=data, payload_type=payload_type, node_id=node.id, node_type=node.type, item_count=item_count)
        await self.artifact_created(artifact)
        return artifact

    async def write_csv_artifact(self, node: WorkflowNode, path: Path, rows: list[dict[str, Any]], payload_type: str) -> ArtifactMetadata:
        artifact = self.store.write_csv(run_id=self.run_id, path=path, rows=rows, payload_type=payload_type, node_id=node.id, node_type=node.type)
        await self.artifact_created(artifact)
        return artifact


def node_dir(ctx: ExecutionContext, node: WorkflowNode) -> Path:
    return ctx.store.node_dir(ctx.run_id, node.id, node.type)


def option(node: WorkflowNode, key: str, default: Any = None) -> Any:
    value = node.options.get(key, default)
    return default if value is None else value


def split_selector(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def option_file_tokens(node: WorkflowNode) -> list[str]:
    return [part.strip() for part in str(node.options.get("file") or "").split(",") if part.strip()]


def payload_from_artifacts(type_name: str, artifacts: list[ArtifactMetadata], data: Any = None, metadata: dict[str, Any] | None = None, item_count: int | None = None) -> TypedPayload:
    return TypedPayload(
        type_name=type_name,
        item_count=len(artifacts) if item_count is None else item_count,
        artifact_ids=[artifact.artifact_id for artifact in artifacts],
        paths=[artifact.path for artifact in artifacts],
        metadata=metadata or {},
        data=data,
    )


def embedded_or_stored_uploads(ctx: ExecutionContext, node: WorkflowNode) -> list[tuple[str, str, str]]:
    embedded = ctx.uploads.get(node.id, [])
    if not embedded:
        file_names = set(option_file_tokens(node))
        if file_names:
            embedded = [item for items in ctx.uploads.values() for item in items if item.name in file_names]
    if embedded:
        return [(item.name, item.type or Path(item.name).suffix.lower().lstrip("."), item.content) for item in embedded]

    results: list[tuple[str, str, str]] = []
    for token in option_file_tokens(node):
        stored = upload_store.get(token)
        if stored is not None:
            results.append((stored.name, stored.type, stored.path.read_text()))
    return results


async def copy_paths_as_artifacts(ctx: ExecutionContext, node: WorkflowNode, paths: list[Path], payload_type: str) -> list[ArtifactMetadata]:
    artifacts: list[ArtifactMetadata] = []
    out_dir = node_dir(ctx, node)
    for index, source in enumerate(paths, start=1):
        destination = out_dir / f"{payload_type.replace(' ', '_').lower()}_{index:04d}{source.suffix or '.pdb'}"
        shutil.copy2(source, destination)
        artifact = ctx.store.register_file(run_id=ctx.run_id, path=destination, payload_type=payload_type, node_id=node.id, node_type=node.type)
        await ctx.artifact_created(artifact)
        artifacts.append(artifact)
    return artifacts


def read_payload_files(ctx: ExecutionContext, payload: TypedPayload) -> list[str]:
    contents: list[str] = []
    for rel_path in payload.paths:
        contents.append(ctx.store.absolute(ctx.run_id, rel_path).read_text())
    return contents


def scores_to_rows(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(score) for score in scores]


def parse_score_files(paths: list[Path]) -> list[dict[str, Any]]:
    scores: list[dict[str, Any]] = []
    for path in paths:
        if path.suffix.lower() != ".json":
            continue
        data = json.loads(path.read_text())
        if isinstance(data, list):
            scores.extend(item for item in data if isinstance(item, dict))
        elif isinstance(data, dict):
            if isinstance(data.get("scores"), list):
                scores.extend(item for item in data["scores"] if isinstance(item, dict))
            else:
                scores.append(data)
    return scores
