from backend.nodes.generation import base as _base
from backend.nodes.generation.RFDiffusionEnzyme import RFDiffusionEnzyme
from backend.nodes.generation.RFDiffusionProteinBinder import RFDiffusionProteinBinder
from backend.nodes.generation.RFDiffusionSMbinder import RFDiffusionSMbinder

run_rfd3_payload = _base.run_rfd3_payload


async def rfdiffusion_smbinder(ctx, node, inputs):
    _base.run_rfd3_payload = run_rfd3_payload
    return await RFDiffusionSMbinder.execute(ctx, node, inputs)


async def rfdiffusion_protein_binder(ctx, node, inputs):
    _base.run_rfd3_payload = run_rfd3_payload
    return await RFDiffusionProteinBinder.execute(ctx, node, inputs)


async def rfdiffusion_enzyme(ctx, node, inputs):
    _base.run_rfd3_payload = run_rfd3_payload
    return await RFDiffusionEnzyme.execute(ctx, node, inputs)
