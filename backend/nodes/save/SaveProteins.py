from backend.nodes.common import option
from backend.nodes.save.base import SaveNode
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class SaveProteins(SaveNode):
    type_name = "SaveProteins"
    title = "Save Proteins"
    description = "Save protein PDB files without score CSV."
    inputs = (P("structures", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"),)
    options = (O("folder", "text", "outputs/proteins", label="Folder Selector"),)
    catalog_order = 280

    @classmethod
    async def execute(cls, ctx, node, inputs):
        structures = inputs["structures"]
        target_dir = ctx.store.run_dir(ctx.run_id) / "saves" / cls.safe_folder(str(option(node, "folder", "outputs/proteins")))
        target_dir.mkdir(parents=True, exist_ok=True)
        for index, rel_path in enumerate(structures.paths, start=1):
            filename = f"structure_{index:04d}.pdb"
            artifact = ctx.store.copy_artifact(run_id=ctx.run_id, source_relative_path=rel_path, destination=target_dir / filename, payload_type=structures.metadata.get("effective_type", structures.type_name), node_id=node.id, node_type=node.type)
            await ctx.artifact_created(artifact)
        await cls.zip_saved_folder(ctx, node, target_dir, "proteins.zip", "Saved Proteins", structures.item_count)
        return {}
