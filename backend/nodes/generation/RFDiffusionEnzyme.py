from backend.nodes.common import copy_paths_as_artifacts, node_dir, option, read_payload_files
from backend.nodes.generation.base import GenerationNode
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class RFDiffusionEnzyme(GenerationNode):
    type_name = "RFDiffusionEnzyme"
    title = "RFDiffusion3 Enzyme"
    description = "RFdiffusion3 enzyme design from a protein-ligand theozyme."
    inputs = (P("complex", "Batch Protein with Ligand", label="Protein with Ligand"), P("ligand", "List of Residues", label="ligand residues"), P("unindex", "List of Residues", label="unindex residues"), P("selectFixedAtoms", "Residues Atoms List", optional=True, label="select_fixed_atoms"), P("selectBuried", "Residues Atoms List", optional=True, label="select_buried"), P("selectExposed", "Residues Atoms List", optional=True, label="select_exposed"))
    options = (O("length", "text", "180-200", required=True), O("nBatches", "int", 1, min_value=1, label="n_batches"), O("diffusionBatchSize", "int", 5, min_value=1, label="diffusion_batch_size"))
    outputs = (P("complexes", "Batch Protein with Ligand", label="Batch Protein with Ligand"),)
    catalog_order = 120

    @classmethod
    async def execute(cls, ctx, node, inputs):
        complex_path = ctx.store.absolute(ctx.run_id, inputs["complex"].paths[0])
        ligand_residues = cls.residue_list(inputs.get("ligand"))
        unindex = cls.residue_list(inputs.get("unindex"))
        work_dir = node_dir(ctx, node)
        payload = {
            "foundryui_enzyme": {
                "input": str(complex_path),
                "ligand": ",".join(ligand_residues),
                "unindex": ",".join(unindex),
                "length": str(option(node, "length", "180-200")),
                "select_fixed_atoms": cls.atom_map(inputs.get("selectFixedAtoms")),
                "select_buried": cls.atom_map(inputs.get("selectBuried")),
                "select_exposed": cls.atom_map(inputs.get("selectExposed")),
            }
        }
        paths = await cls.run_rfd3_payload(
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
