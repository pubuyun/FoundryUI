from __future__ import annotations

from backend.foundry_tools.rfd3 import run_rfd3_design
from backend.nodes.common import ExecutionContext, copy_paths_as_artifacts, node_dir, option, read_payload_files
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def rfdiffusion_smbinder(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    ligand = inputs["ligand"]
    ligand_path = ctx.store.absolute(ctx.run_id, ligand.paths[0])
    work_dir = node_dir(ctx, node)
    paths = await run_rfd3_design(
        run_id=ctx.run_id,
        node_id=node.id,
        node_type=node.type,
        work_dir=work_dir,
        ligand_path=ligand_path,
        length=option(node, "length"),
        n_batches=int(option(node, "nBatches", 1)),
        diffusion_batch_size=int(option(node, "diffusionBatchSize", 5)),
        select_fixed_atoms=inputs.get("selectFixedAtoms", TypedPayload(type_name="List of Atoms", data=[])).data or [],
        select_buried=inputs.get("selectBuried", TypedPayload(type_name="List of Atoms", data=[])).data or [],
        select_exposed=inputs.get("selectExposed", TypedPayload(type_name="List of Atoms", data=[])).data or [],
        registry=ctx.registry,
        store=ctx.store,
    )
    if not paths:
        raise BackendError(make_error("NO_RFD3_OUTPUTS", "RFDiffusionSMbinder did not produce PDB outputs.", run_id=ctx.run_id, node_id=node.id, node_type=node.type))
    artifacts = await copy_paths_as_artifacts(ctx, node, paths, "Batch Protein with Ligand")
    data = read_payload_files(ctx, TypedPayload(type_name="Batch Protein with Ligand", paths=[artifact.path for artifact in artifacts]))
    return {"complexes": TypedPayload(type_name="Batch Protein with Ligand", item_count=len(artifacts), artifact_ids=[a.artifact_id for a in artifacts], paths=[a.path for a in artifacts], data=data)}
