from __future__ import annotations

from backend.foundry_tools.rfd3 import run_rfd3_design, run_rfd3_payload
from backend.bio.pdb import first_residue_name
from backend.nodes.common import ExecutionContext, copy_paths_as_artifacts, node_dir, option, read_payload_files
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def rfdiffusion_smbinder(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    ligand = inputs["ligand"]
    ligand_path = ctx.store.absolute(ctx.run_id, ligand.paths[0])
    ligand_residue_name = str(ligand.metadata.get("residue_name") or first_residue_name(ligand_path.read_text()))
    work_dir = node_dir(ctx, node)
    paths = await run_rfd3_design(
        run_id=ctx.run_id,
        node_id=node.id,
        node_type=node.type,
        work_dir=work_dir,
        ligand_path=ligand_path,
        ligand_residue_name=ligand_residue_name,
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


async def rfdiffusion_protein_binder(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    protein_path = ctx.store.absolute(ctx.run_id, inputs["protein"].paths[0])
    work_dir = node_dir(ctx, node)
    payload = {
        "foundryui_protein_binder": {
            "dialect": int(option(node, "dialect", 2)),
            "infer_ori_strategy": "hotspots",
            "input": str(protein_path),
            "contig": str(option(node, "contig", "")),
            "select_hotspots": _atom_map(inputs["selectHotspots"]),
            "is_non_loopy": _bool_option(option(node, "isNonLoopy", True)),
        }
    }
    paths = await run_rfd3_payload(
        run_id=ctx.run_id,
        node_id=node.id,
        node_type=node.type,
        work_dir=work_dir,
        out_dir=work_dir / "rfd3_outputs",
        input_json=work_dir / "protein_binder_design.json",
        payload=payload,
        n_batches=int(option(node, "nBatches", 1)),
        diffusion_batch_size=int(option(node, "diffusionBatchSize", 5)),
        overrides=["inference_sampler.step_scale=3", "inference_sampler.gamma_0=0.2"],
        registry=ctx.registry,
        store=ctx.store,
    )
    if not paths:
        raise BackendError(make_error("NO_RFD3_OUTPUTS", "RFDiffusionProteinBinder did not produce PDB outputs.", run_id=ctx.run_id, node_id=node.id, node_type=node.type))
    artifacts = await copy_paths_as_artifacts(ctx, node, paths, "Batch Protein")
    data = read_payload_files(ctx, TypedPayload(type_name="Batch Protein", paths=[artifact.path for artifact in artifacts]))
    return {"batchProtein": TypedPayload(type_name="Batch Protein", item_count=len(artifacts), artifact_ids=[a.artifact_id for a in artifacts], paths=[a.path for a in artifacts], data=data)}


async def rfdiffusion_enzyme(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    complex_path = ctx.store.absolute(ctx.run_id, inputs["complex"].paths[0])
    ligand_residues = _residue_list(inputs.get("ligand"))
    unindex = _residue_list(inputs.get("unindex"))
    work_dir = node_dir(ctx, node)
    payload = {
        "foundryui_enzyme": {
            "input": str(complex_path),
            "ligand": ",".join(ligand_residues),
            "unindex": ",".join(unindex),
            "length": str(option(node, "length", "180-200")),
            "select_fixed_atoms": _atom_map(inputs["selectFixedAtoms"]),
            "select_buried": _atom_map(inputs["selectBuried"]),
            "select_exposed": _atom_map(inputs["selectExposed"]),
        }
    }
    paths = await run_rfd3_payload(
        run_id=ctx.run_id,
        node_id=node.id,
        node_type=node.type,
        work_dir=work_dir,
        out_dir=work_dir / "rfd3_outputs",
        input_json=work_dir / "enzyme_design.json",
        payload=payload,
        n_batches=int(option(node, "nBatches", 1)),
        diffusion_batch_size=int(option(node, "diffusionBatchSize", 5)),
        registry=ctx.registry,
        store=ctx.store,
    )
    if not paths:
        raise BackendError(make_error("NO_RFD3_OUTPUTS", "RFDiffusionEnzyme did not produce PDB outputs.", run_id=ctx.run_id, node_id=node.id, node_type=node.type))
    artifacts = await copy_paths_as_artifacts(ctx, node, paths, "Batch Protein with Ligand")
    data = read_payload_files(ctx, TypedPayload(type_name="Batch Protein with Ligand", paths=[artifact.path for artifact in artifacts]))
    return {"complexes": TypedPayload(type_name="Batch Protein with Ligand", item_count=len(artifacts), artifact_ids=[a.artifact_id for a in artifacts], paths=[a.path for a in artifacts], data=data)}


def _atom_map(payload: TypedPayload) -> dict[str, str]:
    data = payload.data or {}
    if isinstance(data, dict):
        return {str(key): str(value) for key, value in data.items()}
    return {}


def _residue_list(payload: TypedPayload | None) -> list[str]:
    if payload is None:
        return []
    if isinstance(payload.data, list):
        return [str(item) for item in payload.data if str(item)]
    if isinstance(payload.data, str):
        return [item.strip() for item in payload.data.split(",") if item.strip()]
    return []


def _bool_option(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"false", "0", "no", "off", ""}
