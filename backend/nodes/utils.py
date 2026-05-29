from backend.nodes.utility.Merge import Merge
from backend.nodes.utility.Protein2Seq import Protein2Seq
from backend.nodes.utility.Split import Split


async def protein_to_seq(ctx, node, inputs):
    return await Protein2Seq.execute(ctx, node, inputs)


async def merge(ctx, node, inputs):
    return await Merge.execute(ctx, node, inputs)


async def split(ctx, node, inputs):
    return await Split.execute(ctx, node, inputs)
