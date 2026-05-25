from __future__ import annotations

from io import StringIO

from Bio.PDB import PDBParser, Superimposer

from backend.bio.pdb import split_pdb_complex
from backend.nodes.common import ExecutionContext, node_dir, payload_from_artifacts, read_payload_files, scores_to_rows
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode

try:
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign
except Exception:  # pragma: no cover
    Chem = None
    rdMolAlign = None


async def calculate_protein_rmsd(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    reference = read_payload_files(ctx, inputs["reference"])[0]
    proteins = read_payload_files(ctx, inputs["batchProtein"])
    scores = [{"protein_rmsd": _protein_ca_rmsd(reference, protein)} for protein in proteins]
    return await _score_output(ctx, node, scores)


async def calculate_ligand_rmsd(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    reference = read_payload_files(ctx, inputs["reference"])[0]
    structures = read_payload_files(ctx, inputs["ligands"])
    scores = []
    for content in structures:
        ligand = split_pdb_complex(content)[1] if inputs["ligands"].type_name in {"Batch Protein with Ligand", "Batch Protein (With Ligand)"} else content
        scores.append({"ligand_rmsd": _ligand_rmsd(reference, ligand)})
    return await _score_output(ctx, node, scores)


async def _score_output(ctx: ExecutionContext, node: WorkflowNode, scores: list[dict[str, float]]) -> dict[str, TypedPayload]:
    out_dir = node_dir(ctx, node)
    json_artifact = await ctx.write_json_artifact(node, out_dir / "scores.json", scores, "Score", item_count=len(scores))
    csv_artifact = await ctx.write_csv_artifact(node, out_dir / "scores.csv", scores_to_rows(scores), "Score")
    return {"score": payload_from_artifacts("Score", [json_artifact, csv_artifact], data=scores, metadata={"score_count": len(scores)}, item_count=len(scores))}


def _protein_ca_rmsd(reference: str, protein: str) -> float:
    parser = PDBParser(QUIET=True)
    ref_structure = parser.get_structure("ref", StringIO(reference))
    mov_structure = parser.get_structure("mov", StringIO(protein))
    ref_atoms = [atom for atom in ref_structure.get_atoms() if atom.get_id() == "CA"]
    mov_atoms = [atom for atom in mov_structure.get_atoms() if atom.get_id() == "CA"]
    count = min(len(ref_atoms), len(mov_atoms))
    if count == 0:
        raise ValueError("Protein RMSD requires CA atoms in both structures.")
    superimposer = Superimposer()
    superimposer.set_atoms(ref_atoms[:count], mov_atoms[:count])
    return round(float(superimposer.rms), 6)


def _ligand_rmsd(reference: str, ligand: str) -> float:
    if Chem is None or rdMolAlign is None:
        raise BackendError(make_error("RDKIT_UNAVAILABLE", "RDKit is required to calculate ligand RMSD."))
    ref_mol = Chem.MolFromPDBBlock(reference, sanitize=False, removeHs=False)
    ligand_mol = Chem.MolFromPDBBlock(ligand, sanitize=False, removeHs=False)
    if ref_mol is None or ligand_mol is None:
        raise ValueError("Ligand RMSD requires parseable ligand PDB content.")
    if ref_mol.GetNumAtoms() != ligand_mol.GetNumAtoms():
        raise ValueError("Ligand RMSD requires matching atom counts.")
    return round(float(rdMolAlign.GetBestRMS(ref_mol, ligand_mol)), 6)
