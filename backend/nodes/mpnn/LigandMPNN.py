from backend.foundry_tools.ligand_mpnn import run_ligand_mpnn
from backend.nodes.common import node_dir, option
from backend.nodes.mpnn.base import MpnnNode
from backend.schemas.payloads import TypedPayload
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class LigandMPNN(MpnnNode):
    type_name = "LigandMPNN"
    title = "Ligand MPNN"
    description = "Ligand-aware sequence design for protein-ligand complexes."
    inputs = (P("complexes", "Batch Protein with Ligand", label="Batch Protein with Ligand"), P("residues", "List of Residues", optional=True, label="List of Residues: fixed/redesigned"))
    options = (O("residueRole", "select", "fixed_residues", choices=("fixed_residues", "redesigned_residues"), label="Residue input role"), O("numberOfBatches", "int", None, required=True, min_value=1, label="number_of_batches", frontend_default=4), O("batchSize", "int", None, required=True, min_value=1, label="batch_size", frontend_default=8), O("seed", "int", 42, min_value=0), O("temperature", "float", 0.05, min_value=0, max_value=5), O("biasAA", "text", "", label="bias_AA"), O("omitAA", "text", "", label="omit_AA"))
    outputs = (P("sequences", "Batch Sequence", label="Batch Sequence"),)
    catalog_order = 130

    @classmethod
    async def execute(cls, ctx, node, inputs):
        input_dir = node_dir(ctx, node) / "inputs"
        input_dir.mkdir(parents=True, exist_ok=True)
        for index, rel_path in enumerate(inputs["complexes"].paths, start=1):
            (input_dir / f"complex_{index:04d}.pdb").write_text(ctx.store.absolute(ctx.run_id, rel_path).read_text())
        paths = await run_ligand_mpnn(
            run_id=ctx.run_id,
            node_id=node.id,
            node_type=node.type,
            work_dir=node_dir(ctx, node),
            input_dir=input_dir,
            residue_role=str(option(node, "residueRole", "fixed_residues")),
            residues=inputs.get("residues", TypedPayload(type_name="List of Residues", data=[])).data or [],
            number_of_batches=int(option(node, "numberOfBatches", 1)),
            batch_size=int(option(node, "batchSize", 1)),
            seed=int(option(node, "seed", 42)),
            temperature=float(option(node, "temperature", 0.05)),
            bias_aa=str(option(node, "biasAA", "")),
            omit_aa=str(option(node, "omitAA", "")),
            registry=ctx.registry,
            store=ctx.store,
        )
        return await cls.collect_fasta(ctx, node, paths, "NO_LIGAND_MPNN_OUTPUTS")
