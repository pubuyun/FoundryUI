from backend.nodes.logic.BinaryLogic import BinaryLogic


async def binary_logic(ctx, node, inputs):
    return await BinaryLogic.execute(ctx, node, inputs)
