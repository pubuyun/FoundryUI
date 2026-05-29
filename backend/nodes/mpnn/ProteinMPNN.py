from backend.foundry_tools.protein_mpnn import run_protein_mpnn
from backend.nodes.common import node_dir, option
from backend.nodes.mpnn.LigandMPNN import LigandMPNN
from backend.schemas.payloads import TypedPayload
from backend.workflow.catalog import PortSpec as P


class ProteinMPNN(LigandMPNN):
    type_name = "ProteinMPNN"
    title = "Protein MPNN"
    description = "Sequence design for protein batches without ligand context."
    inputs = (P("batchProtein", "Batch Protein", label="Batch Protein"), P("residues", "List of Residues", optional=True, label="List of Residues: fixed/redesigned"))
    catalog_order = 140

    @classmethod
    async def execute(cls, ctx, node, inputs):
        input_dir = node_dir(ctx, node) / "inputs"
        input_dir.mkdir(parents=True, exist_ok=True)
        for index, rel_path in enumerate(inputs["batchProtein"].paths, start=1):
            (input_dir / f"protein_{index:04d}.pdb").write_text(ctx.store.absolute(ctx.run_id, rel_path).read_text())
        paths = await run_protein_mpnn(
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
        return await cls.collect_fasta(ctx, node, paths, "NO_PROTEIN_MPNN_OUTPUTS")
