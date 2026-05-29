from io import StringIO

from Bio.PDB import PDBParser, Superimposer
from backend.nodes.common import read_payload_files
from backend.nodes.scoring.base import ScoringNode
from backend.workflow.catalog import PortSpec as P


class CalculateProteinRMSD(ScoringNode):
    type_name = "CalculateProteinRMSD"
    title = "Calculate Protein RMSD"
    description = "Calculate CA RMSD from a reference protein to a protein batch."
    inputs = (P("reference", "Protein", label="Protein (Ref)"), P("batchProtein", "Batch Protein", label="Batch Protein"))
    outputs = (P("score", "Score", label="Score"),)
    catalog_order = 170

    @classmethod
    async def execute(cls, ctx, node, inputs):
        reference = read_payload_files(ctx, inputs["reference"])[0]
        proteins = read_payload_files(ctx, inputs["batchProtein"])
        scores = [{"protein_rmsd": cls.protein_ca_rmsd(reference, protein)} for protein in proteins]
        return await cls.score_output(ctx, node, scores)

    @staticmethod
    def protein_ca_rmsd(reference: str, protein: str) -> float:
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
