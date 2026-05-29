from backend.nodes.common import copy_paths_as_artifacts, node_dir, option, read_payload_files
from backend.nodes.generation.base import GenerationNode
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class RFDiffusionProteinBinder(GenerationNode):
    type_name = "RFDiffusionProteinBinder"
    title = "RFDiffusion3 Protein Binder"
    description = "RFdiffusion3 protein binder generation using hotspot atoms."
    inputs = (P("protein", "Protein", label="Protein"), P("selectHotspots", "Residues Atoms List", label="select_hotspots"))
    options = (O("dialect", "int", 2, min_value=1), O("contig", "text", "40-120,/0,A1-100", required=True), O("isNonLoopy", "bool", True, label="is_non_loopy"), O("nBatches", "int", 1, min_value=1, label="n_batches"), O("diffusionBatchSize", "int", 5, min_value=1, label="diffusion_batch_size"))
    outputs = (P("batchProtein", "Batch Protein", label="Batch Protein"),)
    catalog_order = 110

    @classmethod
    async def execute(cls, ctx, node, inputs):
        protein_path = ctx.store.absolute(ctx.run_id, inputs["protein"].paths[0])
        work_dir = node_dir(ctx, node)
        payload = {
            "foundryui_protein_binder": {
                "dialect": int(option(node, "dialect", 2)),
                "infer_ori_strategy": "hotspots",
                "input": str(protein_path),
                "contig": str(option(node, "contig", "")),
                "select_hotspots": cls.atom_map(inputs["selectHotspots"]),
                "is_non_loopy": cls.bool_option(option(node, "isNonLoopy", True)),
            }
        }
        paths = await cls.run_rfd3_payload(
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
