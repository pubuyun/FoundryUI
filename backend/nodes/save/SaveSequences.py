from backend.bio.fasta import write_fasta
from backend.nodes.common import option
from backend.nodes.save.base import SaveNode
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class SaveSequences(SaveNode):
    type_name = "SaveSequences"
    title = "Save Sequences"
    description = "Save batch sequences as FASTA."
    inputs = (P("sequences", "Batch Sequence", label="Batch Sequence"),)
    options = (O("folder", "text", "outputs/sequences", label="Folder Selector"),)
    catalog_order = 290

    @classmethod
    async def execute(cls, ctx, node, inputs):
        target_dir = ctx.store.run_dir(ctx.run_id) / "saves" / cls.safe_folder(str(option(node, "folder", "outputs/sequences")))
        target_dir.mkdir(parents=True, exist_ok=True)
        sequences = inputs["sequences"].data or []
        await ctx.write_text_artifact(node, target_dir / "sequences.fasta", write_fasta(sequences), "Batch Sequence", "text/x-fasta", item_count=len(sequences))
        await cls.zip_saved_folder(ctx, node, target_dir, "sequences.zip", "Saved Sequences", len(sequences))
        return {}
