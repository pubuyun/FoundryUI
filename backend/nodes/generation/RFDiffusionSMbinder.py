from backend.bio.pdb import first_residue_name
from backend.foundry_tools.rfd3 import run_rfd3_design
from backend.nodes.common import copy_paths_as_artifacts, node_dir, option, read_payload_files
from backend.nodes.generation.base import GenerationNode
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class RFDiffusionSMbinder(GenerationNode):
    type_name = "RFDiffusionSMbinder"
    title = "RFDiffusion3 SM Binder"
    description = "RFdiffusion3 small-molecule binder generation."
    inputs = (P("ligand", "Ligand", label="Ligand"), P("selectFixedAtoms", "List of Atoms", optional=True, label="select_fixed_atoms"), P("selectBuried", "List of Atoms", optional=True, label="select_buried"), P("selectExposed", "List of Atoms", optional=True, label="select_exposed"))
    options = (O("length", "text", "50-200", required=True), O("nBatches", "int", 1, min_value=1, label="n_batches"), O("diffusionBatchSize", "int", 5, min_value=1, label="diffusion_batch_size"))
    outputs = (P("complexes", "Batch Protein with Ligand", label="Batch Protein with Ligand"),)
    catalog_order = 100

    @classmethod
    async def execute(cls, ctx, node, inputs):
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
