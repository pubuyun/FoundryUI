from __future__ import annotations

from backend.bio.fasta import write_fasta
from backend.bio.pdb import merge_pdb_structures, split_pdb_complex
from backend.bio.sequences import pdb_to_sequence
from backend.nodes.common import ExecutionContext, node_dir, payload_from_artifacts, read_payload_files
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def protein_to_seq(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    proteins = read_payload_files(ctx, inputs["batchProtein"])
    sequences = [{"id": f"sequence_{index:04d}", "sequence": pdb_to_sequence(content)} for index, content in enumerate(proteins, start=1)]
    artifact = await ctx.write_text_artifact(node, node_dir(ctx, node) / "sequences.fasta", write_fasta(sequences), "Batch Sequence", "text/x-fasta", item_count=len(sequences))
    return {"sequences": payload_from_artifacts("Batch Sequence", [artifact], data=sequences)}


async def merge(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    left_payload = inputs.get("inputA") or inputs.get("batchProtein")
    right_payload = inputs.get("inputB") or inputs.get("ligand")
    if left_payload is None or right_payload is None:
        raise BackendError(make_error("MISSING_MERGE_INPUT", "Merge requires two connected inputs.", run_id=ctx.run_id, node_id=node.id, node_type=node.type))
    left_items = read_payload_files(ctx, left_payload)
    right_items = read_payload_files(ctx, right_payload)
    count = _merged_count(left_payload, right_payload, node, ctx.run_id)
    out_dir = node_dir(ctx, node)
    artifacts = []
    complexes = []
    output_type = "Batch Protein" if _protein_only(left_payload) and _protein_only(right_payload) else "Batch Protein (With Ligand)"
    for index in range(count):
        left = left_items[0 if left_payload.item_count <= 1 else index]
        right = right_items[0 if right_payload.item_count <= 1 else index]
        complex_pdb = merge_pdb_structures([left, right])
        artifact = await ctx.write_text_artifact(node, out_dir / f"merged_{index + 1:04d}.pdb", complex_pdb, output_type, "chemical/x-pdb")
        artifacts.append(artifact)
        complexes.append(complex_pdb)
    return {"complexes": payload_from_artifacts(output_type, artifacts, data=complexes)}


def _merged_count(left: TypedPayload, right: TypedPayload, node: WorkflowNode, run_id: str) -> int:
    left_count = max(left.item_count or len(left.paths) or 1, 1)
    right_count = max(right.item_count or len(right.paths) or 1, 1)
    if left_count == right_count:
        return left_count
    if left_count == 1:
        return right_count
    if right_count == 1:
        return left_count
    raise BackendError(
        make_error(
            "MERGE_LENGTH_MISMATCH",
            "Merge inputs must have the same item count unless one input is single.",
            run_id=run_id,
            node_id=node.id,
            node_type=node.type,
            details={"left_count": left_count, "right_count": right_count},
        )
    )


def _protein_only(payload: TypedPayload) -> bool:
    return payload.type_name in {"Protein", "Batch Protein"}


async def split(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    complexes = read_payload_files(ctx, inputs["complexes"])
    out_dir = node_dir(ctx, node)
    protein_artifacts = []
    ligand_artifacts = []
    proteins = []
    ligands = []
    for index, content in enumerate(complexes, start=1):
        protein, ligand = split_pdb_complex(content)
        protein_artifact = await ctx.write_text_artifact(node, out_dir / f"protein_{index:04d}.pdb", protein, "Batch Protein", "chemical/x-pdb")
        ligand_artifact = await ctx.write_text_artifact(node, out_dir / f"ligand_{index:04d}.pdb", ligand, "Batch Ligand", "chemical/x-pdb")
        protein_artifacts.append(protein_artifact)
        ligand_artifacts.append(ligand_artifact)
        proteins.append(protein)
        ligands.append(ligand)
    return {
        "batchLigand": payload_from_artifacts("Batch Ligand", ligand_artifacts, data=ligands),
        "batchProtein": payload_from_artifacts("Batch Protein", protein_artifacts, data=proteins),
    }
