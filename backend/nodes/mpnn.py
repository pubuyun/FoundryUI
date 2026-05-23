from __future__ import annotations

from backend.bio.fasta import parse_fasta, write_fasta
from backend.foundry_tools.ligand_mpnn import run_ligand_mpnn
from backend.foundry_tools.protein_mpnn import run_protein_mpnn
from backend.nodes.common import ExecutionContext, node_dir, option
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def ligand_mpnn(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    input_dir = node_dir(ctx, node) / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    for index, rel_path in enumerate(inputs["complexes"].paths, start=1):
        (input_dir / f"complex_{index:04d}.pdb").write_text(ctx.store.absolute(ctx.run_id, rel_path).read_text())
    paths = await run_ligand_mpnn(
        run_id=ctx.run_id,
        node_id=node.id,
        node_type=node.type,
        work_dir=node_dir(ctx, node),
        input_dir=input_dir,
        residue_role=str(option(node, "residueRole", "fixed_residues")),
        residues=inputs.get("residues", TypedPayload(type_name="List of Residues", data=[])).data or [],
        number_of_batches=int(option(node, "numberOfBatches", 1)),
        batch_size=int(option(node, "batchSize", 1)),
        seed=int(option(node, "seed", 42)),
        temperature=float(option(node, "temperature", 0.05)),
        bias_aa=str(option(node, "biasAA", "")),
        omit_aa=str(option(node, "omitAA", "")),
        registry=ctx.registry,
        store=ctx.store,
    )
    return await _collect_fasta(ctx, node, paths, "NO_LIGAND_MPNN_OUTPUTS")


async def protein_mpnn(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    input_dir = node_dir(ctx, node) / "inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    for index, rel_path in enumerate(inputs["batchProtein"].paths, start=1):
        (input_dir / f"protein_{index:04d}.pdb").write_text(ctx.store.absolute(ctx.run_id, rel_path).read_text())
    paths = await run_protein_mpnn(
        run_id=ctx.run_id,
        node_id=node.id,
        node_type=node.type,
        work_dir=node_dir(ctx, node),
        input_dir=input_dir,
        residue_role=str(option(node, "residueRole", "fixed_residues")),
        residues=inputs.get("residues", TypedPayload(type_name="List of Residues", data=[])).data or [],
        number_of_batches=int(option(node, "numberOfBatches", 1)),
        batch_size=int(option(node, "batchSize", 1)),
        seed=int(option(node, "seed", 42)),
        temperature=float(option(node, "temperature", 0.05)),
        bias_aa=str(option(node, "biasAA", "")),
        omit_aa=str(option(node, "omitAA", "")),
        registry=ctx.registry,
        store=ctx.store,
    )
    return await _collect_fasta(ctx, node, paths, "NO_PROTEIN_MPNN_OUTPUTS")


async def _collect_fasta(ctx: ExecutionContext, node: WorkflowNode, paths, error_code: str) -> dict[str, TypedPayload]:
    if not paths:
        raise BackendError(make_error(error_code, f"{node.type} did not produce FASTA outputs.", run_id=ctx.run_id, node_id=node.id, node_type=node.type))
    records = []
    for path in paths:
        records.extend(parse_fasta(path.read_text()))
    data = [{"id": record.id, "sequence": record.sequence, "description": record.description} for record in records]
    artifact = await ctx.write_text_artifact(node, node_dir(ctx, node) / "sequences.fasta", write_fasta(data), "Batch Sequence", "text/x-fasta", item_count=len(data))
    return {"sequences": TypedPayload(type_name="Batch Sequence", item_count=len(data), artifact_ids=[artifact.artifact_id], paths=[artifact.path], data=data)}
