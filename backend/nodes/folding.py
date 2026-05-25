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
    input_mode = str(option(node, "inputMode", "Concat inputs"))
    ligand_smiles_list = _ligand_smiles_list(ctx, ligand)
    ligand_smiles = None
    if ligand is not None:
        ligand_smiles = ligand_smiles_list[0] if ligand_smiles_list else ""
    cofold_jobs = _cofold_jobs(ctx, node, inputs["sequences"], ligand) if input_mode == "Co-folding" else None
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
        cofold_jobs=cofold_jobs,
    )
    if not structure_paths:
        raise BackendError(make_error("NO_RF3_OUTPUTS", "RosettaFold3 did not produce PDB outputs.", run_id=ctx.run_id, node_id=node.id, node_type=node.type))
    payload_type = "Batch Protein (With Ligand)" if ligand_path or ligand_smiles_list else "Batch Protein"
    artifacts = await copy_paths_as_artifacts(ctx, node, structure_paths, payload_type)
    structures = read_payload_files(ctx, TypedPayload(type_name=payload_type, paths=[artifact.path for artifact in artifacts]))
    if not scores:
        if cofold_jobs is not None:
            scores = [{"pLDDT": None, "length": sum(len(str(component.get("seq", ""))) for component in components)} for components in cofold_jobs[: len(artifacts)]]
        else:
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


def _ligand_smiles_list(ctx: ExecutionContext, ligand: TypedPayload | None) -> list[str]:
    if ligand is None:
        return []
    smiles_list = ligand.metadata.get("smiles_list")
    if isinstance(smiles_list, list):
        values = [str(value).strip() for value in smiles_list if str(value).strip()]
        if values:
            return values
    smiles = str(ligand.metadata.get("smiles") or "").strip()
    if smiles:
        return [smiles]
    values: list[str] = []
    for path in ligand.paths:
        ligand_path = ctx.store.absolute(ctx.run_id, path)
        if ligand_path.is_file():
            converted = pdb_to_smiles(ligand_path.read_text()).strip()
            if converted:
                values.append(converted)
    return values


def _cofold_jobs(ctx: ExecutionContext, node: WorkflowNode, sequences: TypedPayload, ligand: TypedPayload | None) -> list[list[dict[str, str]]]:
    sequence_sources = [_sequence_items(payload) for payload in _payload_sources(sequences)]
    sequence_sources = [items for items in sequence_sources if items]
    sequence_lengths = [len(items) for items in sequence_sources]
    if not sequence_lengths:
        return []
    ligand_sources = [_ligand_source(ctx, payload) for payload in _payload_sources(ligand)] if ligand is not None else []
    batch_ligand_lengths = [len(source["smiles"]) for source in ligand_sources if not source["reusable"]]
    job_count = max([*sequence_lengths, *batch_ligand_lengths])
    if any(length not in {1, job_count} for length in sequence_lengths):
        _raise_cofold_length_error(ctx, node, "sequences", sequence_lengths, job_count)

    for source in ligand_sources:
        if not source["reusable"] and len(source["smiles"]) != job_count:
            _raise_cofold_length_error(ctx, node, "ligand", [len(source["smiles"])], job_count)

    jobs: list[list[dict[str, str]]] = []
    for index in range(job_count):
        components: list[dict[str, str]] = []
        for source_index, items in enumerate(sequence_sources):
            item = items[0] if len(items) == 1 else items[index]
            sequence = str(item.get("sequence") or "").strip()
            if sequence:
                components.append({"seq": sequence, "chain_id": _chain_id(source_index)})
        for source in ligand_sources:
            smiles_values = source["smiles"] if source["reusable"] else source["smiles"][index : index + 1]
            components.extend({"smiles": smiles} for smiles in smiles_values if smiles)
        jobs.append(components)
    return jobs


def _payload_sources(payload: TypedPayload | None) -> list[TypedPayload]:
    if payload is None:
        return []
    combined = payload.metadata.get("combined_payloads")
    if isinstance(combined, list) and combined:
        return [TypedPayload.model_validate(item) for item in combined]
    return [payload]


def _sequence_items(payload: TypedPayload) -> list[dict]:
    if isinstance(payload.data, list):
        return [item for item in payload.data if isinstance(item, dict)]
    return [payload.data] if isinstance(payload.data, dict) else []


def _ligand_source(ctx: ExecutionContext, payload: TypedPayload) -> dict[str, object]:
    smiles = _ligand_smiles_list(ctx, payload)
    reusable = payload.type_name == "Ligand"
    if reusable and smiles:
        smiles = smiles[:1]
    return {"reusable": reusable, "smiles": smiles}


def _raise_cofold_length_error(ctx: ExecutionContext, node: WorkflowNode, input_key: str, lengths: list[int], expected: int) -> None:
    raise BackendError(
        make_error(
            "RF3_COFOLD_LENGTH_MISMATCH",
            "Co-folding inputs connected to the same RF3 port must have matching batch lengths.",
            run_id=ctx.run_id,
            node_id=node.id,
            node_type=node.type,
            interface_key=input_key,
            details={"expected_length": expected, "actual_lengths": lengths},
        )
    )


def _chain_id(index: int) -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if index < len(letters):
        return letters[index]
    return f"A{index - len(letters) + 1}"
