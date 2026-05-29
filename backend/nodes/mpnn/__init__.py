from backend.nodes.mpnn.LigandMPNN import LigandMPNN
from backend.nodes.mpnn.ProteinMPNN import ProteinMPNN


async def ligand_mpnn(ctx, node, inputs):
    return await LigandMPNN.execute(ctx, node, inputs)


async def protein_mpnn(ctx, node, inputs):
    return await ProteinMPNN.execute(ctx, node, inputs)
