from backend.nodes.filter.FilterAtomsChirality import FilterAtomsChirality
from backend.nodes.filter.FilterByScore import FilterByScore
from backend.nodes.filter.FilterChirality import FilterChirality
from backend.nodes.registry import FoundryNode


async def filter_by_score(ctx, node, inputs):
    return await FilterByScore.execute(ctx, node, inputs)


async def filter_chirality(ctx, node, inputs):
    return await FilterChirality.execute(ctx, node, inputs)


async def filter_atoms_chirality(ctx, node, inputs):
    return await FilterAtomsChirality.execute(ctx, node, inputs)


def ensure_score_alignment(ctx, node, structures, scores, input_keys):
    return FoundryNode.ensure_score_alignment(ctx, node, structures, scores, input_keys)


def _score_value(score, metric, default):
    return FilterByScore.score_value(score, metric, default)
