from __future__ import annotations

from pathlib import Path

from backend.bio.fasta import parse_fasta, write_fasta
from backend.bio.ligand import standardize_ligand_pdb
from backend.bio.pdb import first_residue_name, rename_residue, validate_pdb
from backend.nodes.common import ExecutionContext, embedded_or_stored_uploads, node_dir, option, payload_from_artifacts
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def ligand_input(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    out_dir = node_dir(ctx, node)
    uploads = embedded_or_stored_uploads(ctx, node)
    if not uploads:
        raise BackendError(make_error("MISSING_LIGAND_FILE", "LigandInput requires an uploaded PDB file.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file"))
    pdbs: list[str] = []
    smiles_values: list[str] = []
    for name, file_type, content in uploads:
        detected = (file_type or Path(name).suffix.lower().lstrip(".")).lower()
        if detected != "pdb":
            raise BackendError(make_error("INVALID_LIGAND_FILE_TYPE", "LigandInput accepts PDB files.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file", details={"file": name}))
        validate_pdb(content)
        pdbs.append(content)
    if len(pdbs) == 1:
        residue_name = ctx.next_ligand_residue_name()
        pdb, smiles = standardize_ligand_pdb(rename_residue(pdbs[0], residue_name), residue_name)
        artifact = await ctx.write_text_artifact(node, out_dir / "ligand.pdb", pdb, "Ligand", "chemical/x-pdb")
        return {"ligand": payload_from_artifacts("Ligand", [artifact], data=pdb, metadata={"residue_name": residue_name, "residue_names": [residue_name], "smiles": smiles, "smiles_list": [smiles], "renamed_residue": True, "standardized": True})}

    artifacts = []
    residue_names = [first_residue_name(pdb) for pdb in pdbs]
    standardized_pdbs = []
    smiles_values = []
    for index, pdb in enumerate(pdbs, start=1):
        standardized, smiles = standardize_ligand_pdb(pdb)
        standardized_pdbs.append(standardized)
        smiles_values.append(smiles)
        artifact = await ctx.write_text_artifact(node, out_dir / f"ligand_{index:04d}.pdb", standardized, "Batch Ligand", "chemical/x-pdb")
        artifacts.append(artifact)
    return {"ligand": payload_from_artifacts("Batch Ligand", artifacts, data=standardized_pdbs, metadata={"residue_names": residue_names, "smiles_list": smiles_values, "renamed_residue": False, "standardized": True})}


async def protein_input(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    uploads = embedded_or_stored_uploads(ctx, node)
    if not uploads:
        raise BackendError(make_error("MISSING_PROTEIN_FILE", "ProteinInput requires uploaded PDB files.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file"))
    out_dir = node_dir(ctx, node)
    artifacts = []
    pdbs: list[str] = []
    for index, (name, file_type, content) in enumerate(uploads, start=1):
        if (file_type or Path(name).suffix.lower().lstrip(".")).lower() != "pdb":
            raise BackendError(make_error("INVALID_PROTEIN_FILE_TYPE", "ProteinInput accepts PDB files.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file", details={"file": name}))
        validate_pdb(content)
        artifact = await ctx.write_text_artifact(node, out_dir / f"protein_{index:04d}.pdb", content, "Batch Protein", "chemical/x-pdb")
        artifacts.append(artifact)
        pdbs.append(content)
    return {"batchProtein": payload_from_artifacts("Batch Protein", artifacts, data=pdbs)}


async def protein_with_ligand_input(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    uploads = embedded_or_stored_uploads(ctx, node)
    if not uploads:
        raise BackendError(make_error("MISSING_COMPLEX_FILE", "ProteinWithLigandInput requires uploaded PDB files.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file"))
    out_dir = node_dir(ctx, node)
    artifacts = []
    pdbs: list[str] = []
    for index, (name, file_type, content) in enumerate(uploads, start=1):
        if (file_type or Path(name).suffix.lower().lstrip(".")).lower() != "pdb":
            raise BackendError(make_error("INVALID_COMPLEX_FILE_TYPE", "ProteinWithLigandInput accepts PDB files.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file", details={"file": name}))
        validate_pdb(content)
        artifact = await ctx.write_text_artifact(node, out_dir / f"complex_{index:04d}.pdb", content, "Batch Protein with Ligand", "chemical/x-pdb")
        artifacts.append(artifact)
        pdbs.append(content)
    return {"complexes": payload_from_artifacts("Batch Protein with Ligand", artifacts, data=pdbs)}


async def sequence_input(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    uploads = embedded_or_stored_uploads(ctx, node)
    if not uploads:
        raise BackendError(make_error("MISSING_FASTA_FILE", "SequenceInput requires uploaded FASTA files.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file"))
    records = []
    for name, file_type, content in uploads:
        if (file_type or Path(name).suffix.lower().lstrip(".")).lower() not in {"fasta", "fa"}:
            raise BackendError(make_error("INVALID_FASTA_FILE_TYPE", "SequenceInput accepts FASTA files.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file", details={"file": name}))
        records.extend(parse_fasta(content))
    data = [{"id": record.id, "sequence": record.sequence, "description": record.description} for record in records]
    artifact = await ctx.write_text_artifact(node, node_dir(ctx, node) / "sequences.fasta", write_fasta(data), "Batch Sequence", "text/x-fasta", item_count=len(data))
    return {"batchSequence": payload_from_artifacts("Batch Sequence", [artifact], data=data, metadata={"sequence_count": len(data)})}
