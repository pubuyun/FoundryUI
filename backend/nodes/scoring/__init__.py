from backend.nodes.scoring.CalculateLigandRMSD import CalculateLigandRMSD
from backend.nodes.scoring.CalculateProteinRMSD import CalculateProteinRMSD


async def calculate_protein_rmsd(ctx, node, inputs):
    return await CalculateProteinRMSD.execute(ctx, node, inputs)


async def calculate_ligand_rmsd(ctx, node, inputs):
    return await CalculateLigandRMSD.execute(ctx, node, inputs)
