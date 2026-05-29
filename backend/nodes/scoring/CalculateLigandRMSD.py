from backend.bio.pdb import split_pdb_complex
from backend.nodes.common import read_payload_files
from backend.nodes.scoring.base import ScoringNode
from backend.schemas.errors import BackendError, make_error
from backend.workflow.catalog import PortSpec as P

try:
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign
except Exception:  # pragma: no cover
    Chem = None
    rdMolAlign = None


class CalculateLigandRMSD(ScoringNode):
    type_name = "CalculateLigandRMSD"
    title = "Calculate Ligand RMSD"
    description = "Calculate ligand RMSD from a reference ligand to ligands or complexes."
    inputs = (P("reference", "Ligand", label="Ligand (Ref)"), P("ligands", "Batch Protein (With Ligand)", label="Batch Protein With Ligand or Batch Ligand"))
    outputs = (P("score", "Score", label="Score"),)
    catalog_order = 180

    @classmethod
    async def execute(cls, ctx, node, inputs):
        reference = read_payload_files(ctx, inputs["reference"])[0]
        structures = read_payload_files(ctx, inputs["ligands"])
        scores = []
        for content in structures:
            ligand = split_pdb_complex(content)[1] if inputs["ligands"].type_name in {"Batch Protein with Ligand", "Batch Protein (With Ligand)"} else content
            scores.append({"ligand_rmsd": cls.ligand_rmsd(reference, ligand)})
        return await cls.score_output(ctx, node, scores)

    @staticmethod
    def ligand_rmsd(reference: str, ligand: str) -> float:
        if Chem is None or rdMolAlign is None:
            raise BackendError(make_error("RDKIT_UNAVAILABLE", "RDKit is required to calculate ligand RMSD."))
        ref_mol = Chem.MolFromPDBBlock(reference, sanitize=False, removeHs=False)
        ligand_mol = Chem.MolFromPDBBlock(ligand, sanitize=False, removeHs=False)
        if ref_mol is None or ligand_mol is None:
            raise ValueError("Ligand RMSD requires parseable ligand PDB content.")
        if ref_mol.GetNumAtoms() != ligand_mol.GetNumAtoms():
            raise ValueError("Ligand RMSD requires matching atom counts.")
        return round(float(rdMolAlign.GetBestRMS(ref_mol, ligand_mol)), 6)
