from backend.bio.pdb import split_pdb_complex
from backend.nodes.common import node_dir, payload_from_artifacts, read_payload_files
from backend.nodes.utility.base import UtilityNode
from backend.workflow.catalog import PortSpec as P


class Split(UtilityNode):
    type_name = "Split"
    title = "Split"
    description = "Split complexes into ligand conformers and proteins."
    inputs = (P("complexes", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"),)
    outputs = (P("batchLigand", "Batch Ligand", label="Batch Ligand"), P("batchProtein", "Batch Protein", label="Batch Protein"))
    catalog_order = 240

    @classmethod
    async def execute(cls, ctx, node, inputs):
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
