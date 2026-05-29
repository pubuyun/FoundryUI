from backend.nodes.common import option
from backend.nodes.save.base import SaveNode
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class SaveLigands(SaveNode):
    type_name = "SaveLigands"
    title = "Save Ligands"
    description = "Save ligand or batch ligand structures as PDB files."
    inputs = (P("ligand", "Ligand", label="(Batch) Ligand"),)
    options = (O("folder", "text", "outputs/ligands", label="Folder Selector"),)
    catalog_order = 300

    @classmethod
    async def execute(cls, ctx, node, inputs):
        ligand = inputs["ligand"]
        target_dir = ctx.store.run_dir(ctx.run_id) / "saves" / cls.safe_folder(str(option(node, "folder", "outputs/ligands")))
        target_dir.mkdir(parents=True, exist_ok=True)
        for index, rel_path in enumerate(ligand.paths, start=1):
            artifact = ctx.store.copy_artifact(run_id=ctx.run_id, source_relative_path=rel_path, destination=target_dir / f"ligand_{index:04d}.pdb", payload_type=ligand.type_name, node_id=node.id, node_type=node.type)
            await ctx.artifact_created(artifact)
        await cls.zip_saved_folder(ctx, node, target_dir, "ligands.zip", "Saved Ligands", ligand.item_count)
        return {}
