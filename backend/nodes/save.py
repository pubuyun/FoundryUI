from __future__ import annotations

from pathlib import Path
import zipfile

from backend.bio.fasta import write_fasta
from backend.nodes.common import ExecutionContext, option, read_payload_files, scores_to_rows
from backend.nodes.filters import ensure_score_alignment
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


def _safe_folder(value: str) -> Path:
    parts = [part for part in Path(value or "outputs").parts if part not in {"", ".", ".."}]
    return Path(*parts) if parts else Path("outputs")


async def save_proteins_with_scores(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    structures = inputs["structures"]
    scores = inputs["score"]
    ensure_score_alignment(ctx, node, structures, scores, ["structures", "score"])
    target_dir = ctx.store.run_dir(ctx.run_id) / "saves" / _safe_folder(str(option(node, "folder", "outputs/proteins")))
    target_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, rel_path in enumerate(structures.paths, start=1):
        filename = f"structure_{index:04d}.pdb"
        artifact = ctx.store.copy_artifact(run_id=ctx.run_id, source_relative_path=rel_path, destination=target_dir / filename, payload_type=structures.metadata.get("effective_type", structures.type_name), node_id=node.id, node_type=node.type)
        await ctx.artifact_created(artifact)
        row = dict(scores.data[index - 1])
        row["pdb_filename"] = filename
        rows.append(row)
    await ctx.write_csv_artifact(node, target_dir / "scores.csv", rows, "Score")
    await _zip_saved_folder(ctx, node, target_dir, "proteins_with_scores.zip", "Saved Proteins With Scores", structures.item_count)
    return {}


async def save_proteins(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    structures = inputs["structures"]
    target_dir = ctx.store.run_dir(ctx.run_id) / "saves" / _safe_folder(str(option(node, "folder", "outputs/proteins")))
    target_dir.mkdir(parents=True, exist_ok=True)
    for index, rel_path in enumerate(structures.paths, start=1):
        filename = f"structure_{index:04d}.pdb"
        artifact = ctx.store.copy_artifact(
            run_id=ctx.run_id,
            source_relative_path=rel_path,
            destination=target_dir / filename,
            payload_type=structures.metadata.get("effective_type", structures.type_name),
            node_id=node.id,
            node_type=node.type,
        )
        await ctx.artifact_created(artifact)
    await _zip_saved_folder(ctx, node, target_dir, "proteins.zip", "Saved Proteins", structures.item_count)
    return {}


async def save_sequences(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    target_dir = ctx.store.run_dir(ctx.run_id) / "saves" / _safe_folder(str(option(node, "folder", "outputs/sequences")))
    target_dir.mkdir(parents=True, exist_ok=True)
    sequences = inputs["sequences"].data or []
    await ctx.write_text_artifact(node, target_dir / "sequences.fasta", write_fasta(sequences), "Batch Sequence", "text/x-fasta", item_count=len(sequences))
    return {}


async def _zip_saved_folder(ctx: ExecutionContext, node: WorkflowNode, target_dir: Path, filename: str, payload_type: str, item_count: int) -> None:
    archive_path = target_dir / filename
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(target_dir.iterdir()):
            if path.is_file() and path != archive_path:
                archive.write(path, path.name)
    artifact = ctx.store.register_file(
        run_id=ctx.run_id,
        path=archive_path,
        payload_type=payload_type,
        node_id=node.id,
        node_type=node.type,
        media_type="application/zip",
        item_count=item_count,
    )
    await ctx.artifact_created(artifact)


async def save_ligands(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    ligand = inputs["ligand"]
    target_dir = ctx.store.run_dir(ctx.run_id) / "saves" / _safe_folder(str(option(node, "folder", "outputs/ligands")))
    target_dir.mkdir(parents=True, exist_ok=True)
    for index, rel_path in enumerate(ligand.paths, start=1):
        artifact = ctx.store.copy_artifact(run_id=ctx.run_id, source_relative_path=rel_path, destination=target_dir / f"ligand_{index:04d}.pdb", payload_type=ligand.type_name, node_id=node.id, node_type=node.type)
        await ctx.artifact_created(artifact)
    return {}
