from backend.bio.fasta import write_fasta
from backend.bio.sequences import pdb_to_sequence
from backend.nodes.common import node_dir, payload_from_artifacts, read_payload_files
from backend.nodes.utility.base import UtilityNode
from backend.workflow.catalog import PortSpec as P


class Protein2Seq(UtilityNode):
    type_name = "Protein2Seq"
    title = "Protein To Sequence"
    description = "Extract batch sequences from a batch protein input."
    inputs = (P("batchProtein", "Batch Protein", label="Batch Protein"),)
    outputs = (P("sequences", "Batch Sequence", label="Batch Sequence"),)
    catalog_order = 220

    @classmethod
    async def execute(cls, ctx, node, inputs):
        proteins = read_payload_files(ctx, inputs["batchProtein"])
        sequences = [{"id": f"sequence_{index:04d}", "sequence": pdb_to_sequence(content)} for index, content in enumerate(proteins, start=1)]
        artifact = await ctx.write_text_artifact(node, node_dir(ctx, node) / "sequences.fasta", write_fasta(sequences), "Batch Sequence", "text/x-fasta", item_count=len(sequences))
        return {"sequences": payload_from_artifacts("Batch Sequence", [artifact], data=sequences)}
