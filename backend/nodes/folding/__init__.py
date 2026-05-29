from backend.nodes.folding import RosettaFold as _rosetta_module
from backend.nodes.folding.RosettaFold import RosettaFold

run_rf3_fold = _rosetta_module.run_rf3_fold


async def rosetta_fold(ctx, node, inputs):
    _rosetta_module.run_rf3_fold = run_rf3_fold
    return await RosettaFold.execute(ctx, node, inputs)
