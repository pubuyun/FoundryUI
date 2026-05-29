from backend.nodes.common import option
from backend.nodes.save.base import SaveNode
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class SaveProteinsWithScores(SaveNode):
    type_name = "SaveProteinsWithScores"
    title = "Save Proteins with Scores"
    description = "Save protein PDB files and score CSV with a PDB filename column."
    inputs = (P("structures", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"), P("score", "Score", label="Score"))
    options = (O("folder", "text", "outputs/proteins", label="Folder Selector"),)
    catalog_order = 270

    @classmethod
    async def execute(cls, ctx, node, inputs):
        structures = inputs["structures"]
        scores = inputs["score"]
        cls.ensure_score_alignment(ctx, node, structures, scores, ["structures", "score"])
        target_dir = ctx.store.run_dir(ctx.run_id) / "saves" / cls.safe_folder(str(option(node, "folder", "outputs/proteins")))
        target_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for index, rel_path in enumerate(structures.paths, start=1):
            filename = f"structure_{index:04d}.pdb"
            artifact = ctx.store.copy_artifact(run_id=ctx.run_id, source_relative_path=rel_path, destination=target_dir / filename, payload_type=structures.metadata.get("effective_type", structures.type_name), node_id=node.id, node_type=node.type)
            await ctx.artifact_created(artifact)
            row = dict(scores.data[index - 1])
            row["pdb_filename"] = filename
            rows.append(row)
        await ctx.write_csv_artifact(node, target_dir / "scores.csv", rows, "Score")
        await cls.zip_saved_folder(ctx, node, target_dir, "proteins_with_scores.zip", "Saved Proteins With Scores", structures.item_count)
        return {}
