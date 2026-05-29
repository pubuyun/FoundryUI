from backend.nodes.save.SaveLigands import SaveLigands
from backend.nodes.save.SaveProteins import SaveProteins
from backend.nodes.save.SaveProteinsWithScores import SaveProteinsWithScores
from backend.nodes.save.SaveSequences import SaveSequences


async def save_proteins_with_scores(ctx, node, inputs):
    return await SaveProteinsWithScores.execute(ctx, node, inputs)


async def save_proteins(ctx, node, inputs):
    return await SaveProteins.execute(ctx, node, inputs)


async def save_sequences(ctx, node, inputs):
    return await SaveSequences.execute(ctx, node, inputs)


async def save_ligands(ctx, node, inputs):
    return await SaveLigands.execute(ctx, node, inputs)
