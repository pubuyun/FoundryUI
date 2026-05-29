from backend.nodes.filter.ChainFilter import ChainFilter
from backend.nodes.selector.AtomSelector import AtomSelector
from backend.nodes.selector.ResidueAtomSelector import ResidueAtomSelector
from backend.nodes.selector.ResidueSelector import ResidueSelector


async def atom_selector(ctx, node, inputs):
    return await AtomSelector.execute(ctx, node, inputs)


async def residue_selector(ctx, node, inputs):
    return await ResidueSelector.execute(ctx, node, inputs)


async def protein_chain_selector(ctx, node, inputs):
    return await ChainFilter.execute(ctx, node, inputs)


async def protein_atom_selector(ctx, node, inputs):
    return await ResidueAtomSelector.execute(ctx, node, inputs)
