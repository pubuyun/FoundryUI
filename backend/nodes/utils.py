from __future__ import annotations

from backend.bio.fasta import write_fasta
from backend.bio.pdb import merge_pdb, split_pdb_complex
from backend.bio.sequences import pdb_to_sequence
from backend.nodes.common import ExecutionContext, node_dir, payload_from_artifacts, read_payload_files
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def protein_to_seq(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    proteins = read_payload_files(ctx, inputs["batchProtein"])
    sequences = [{"id": f"sequence_{index:04d}", "sequence": pdb_to_sequence(content)} for index, content in enumerate(proteins, start=1)]
    artifact = await ctx.write_text_artifact(node, node_dir(ctx, node) / "sequences.fasta", write_fasta(sequences), "Batch Sequence", "text/x-fasta", item_count=len(sequences))
    return {"sequences": payload_from_artifacts("Batch Sequence", [artifact], data=sequences)}


async def merge(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    ligand_payload = inputs["ligand"]
    protein_payload = inputs["batchProtein"]
    ligands = read_payload_files(ctx, ligand_payload)
    proteins = read_payload_files(ctx, protein_payload)
    out_dir = node_dir(ctx, node)
    artifacts = []
    complexes = []
    for index, protein in enumerate(proteins, start=1):
        ligand = ligands[min(index - 1, len(ligands) - 1)]
        complex_pdb = merge_pdb(protein, ligand)
        artifact = await ctx.write_text_artifact(node, out_dir / f"complex_{index:04d}.pdb", complex_pdb, "Batch Protein (With Ligand)", "chemical/x-pdb")
        artifacts.append(artifact)
        complexes.append(complex_pdb)
    return {"complexes": payload_from_artifacts("Batch Protein (With Ligand)", artifacts, data=complexes)}


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
