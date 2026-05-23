from __future__ import annotations

from backend.bio.ligand import pdb_to_smiles
from backend.foundry_tools.rf3 import run_rf3_fold
from backend.nodes.common import ExecutionContext, copy_paths_as_artifacts, node_dir, option, payload_from_artifacts, read_payload_files, scores_to_rows
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def rosetta_fold(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    work_dir = node_dir(ctx, node)
    sequences = inputs["sequences"].data or []
    ligand = inputs.get("ligand")
    ligand_path = ctx.store.absolute(ctx.run_id, ligand.paths[0]) if ligand is not None and ligand.paths else None
    ligand_smiles = None
    if ligand is not None:
        ligand_smiles = str(ligand.metadata.get("smiles") or "")
        if not ligand_smiles and ligand_path is not None:
            ligand_smiles = pdb_to_smiles(ligand_path.read_text())
    structure_paths, scores = await run_rf3_fold(
        run_id=ctx.run_id,
        node_id=node.id,
        node_type=node.type,
        work_dir=work_dir,
        sequences=sequences,
        ligand_smiles=ligand_smiles,
        early_stopping_plddt_threshold=float(option(node, "earlyStoppingPlddtThreshold", 0.5)),
        diffusion_batch_size=int(option(node, "diffusionBatchSize", 5)),
        num_steps=int(option(node, "numSteps", 50)),
        seed=int(option(node, "seed", 42)),
        registry=ctx.registry,
        store=ctx.store,
    )
    if not structure_paths:
        raise BackendError(make_error("NO_RF3_OUTPUTS", "RosettaFold3 did not produce PDB outputs.", run_id=ctx.run_id, node_id=node.id, node_type=node.type))
    payload_type = "Batch Protein with Ligand" if ligand_path else "Batch Protein"
    artifacts = await copy_paths_as_artifacts(ctx, node, structure_paths, payload_type)
    structures = read_payload_files(ctx, TypedPayload(type_name=payload_type, paths=[artifact.path for artifact in artifacts]))
    if not scores:
        scores = [{"pLDDT": None, "length": len(str(item.get("sequence", "")))} for item in sequences[: len(artifacts)]]
    if len(scores) != len(artifacts):
        raise BackendError(
            make_error(
                "SCORE_LENGTH_MISMATCH",
                "Structure and score list lengths do not match.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                details={"input_keys": ["structures", "score"], "expected_length": len(artifacts), "actual_length": len(scores)},
            )
        )
    score_json = await ctx.write_json_artifact(node, work_dir / "scores.json", scores, "Score", item_count=len(scores))
    score_csv = await ctx.write_csv_artifact(node, work_dir / "scores.csv", scores_to_rows(scores), "Score")
    return {
        "structures": payload_from_artifacts(payload_type, artifacts, data=structures, metadata={"effective_type": payload_type}),
        "score": payload_from_artifacts("Score", [score_json, score_csv], data=scores, item_count=len(scores)),
    }
