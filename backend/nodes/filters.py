from __future__ import annotations

from backend.bio.ligand import ligand_matches_smiles_chirality
from backend.bio.pdb import split_pdb_complex
from backend.nodes.common import ExecutionContext, node_dir, option, payload_from_artifacts, read_payload_files, scores_to_rows
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


def ensure_score_alignment(ctx: ExecutionContext, node: WorkflowNode, structures: TypedPayload, scores: TypedPayload, input_keys: list[str]) -> None:
    expected = structures.item_count
    actual = scores.item_count
    if expected != actual:
        raise BackendError(
            make_error(
                "SCORE_LENGTH_MISMATCH",
                "Structure and score list lengths do not match.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                details={"input_keys": input_keys, "expected_length": expected, "actual_length": actual},
            )
        )


def _score_value(score: dict, metric: str, default: float) -> float:
    value = score.get(metric, default)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


async def filter_by_score(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    structures = inputs["structures"]
    score_payload = inputs["score"]
    ensure_score_alignment(ctx, node, structures, score_payload, ["structures", "score"])
    scores = list(score_payload.data or [])
    metric = str(option(node, "metric", "pLDDT"))
    mode = str(option(node, "mode", "Is largest top"))
    threshold = float(option(node, "threshold", 10))

    indexed = list(enumerate(scores))
    if mode == "Is largest top":
        keep = {index for index, _ in sorted(indexed, key=lambda item: _score_value(item[1], metric, float("-inf")), reverse=True)[: int(threshold)]}
    elif mode == "Is smallest top":
        keep = {index for index, _ in sorted(indexed, key=lambda item: _score_value(item[1], metric, float("inf")))[: int(threshold)]}
    elif mode == "Higher than":
        keep = {index for index, score in indexed if _score_value(score, metric, float("-inf")) > threshold}
    else:
        keep = {index for index, score in indexed if _score_value(score, metric, float("inf")) < threshold}

    out_dir = node_dir(ctx, node)
    filtered_artifacts = []
    filtered_structures = []
    source_contents = read_payload_files(ctx, structures)
    filtered_scores = []
    for new_index, old_index in enumerate(sorted(keep), start=1):
        content = source_contents[old_index]
        filtered_structures.append(content)
        filtered_scores.append(scores[old_index])
        artifact = await ctx.write_text_artifact(node, out_dir / f"structure_{new_index:04d}.pdb", content, structures.metadata.get("effective_type", "Batch Structure"), "chemical/x-pdb")
        filtered_artifacts.append(artifact)
    json_artifact = await ctx.write_json_artifact(node, out_dir / "scores.json", filtered_scores, "Score", item_count=len(filtered_scores))
    csv_artifact = await ctx.write_csv_artifact(node, out_dir / "scores.csv", scores_to_rows(filtered_scores), "Score")
    return {
        "structures": payload_from_artifacts(structures.type_name, filtered_artifacts, data=filtered_structures, metadata=structures.metadata),
        "score": payload_from_artifacts("Score", [json_artifact, csv_artifact], data=filtered_scores, metadata={"score_count": len(filtered_scores)}, item_count=len(filtered_scores)),
    }


async def filter_chirality(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    complexes = inputs["complexes"]
    scores = inputs.get("score")
    if scores is not None:
        ensure_score_alignment(ctx, node, complexes, scores, ["complexes", "score"])
    contents = read_payload_files(ctx, complexes)
    smiles = _chirality_smiles(ctx, node)
    keep = []
    for index, content in enumerate(contents):
        _, complex_ligand = split_pdb_complex(content)
        try:
            matches = ligand_matches_smiles_chirality(complex_ligand, smiles)
        except ValueError as exc:
            raise BackendError(
                make_error(
                    "INVALID_CHIRALITY_SMILES",
                    str(exc),
                    run_id=ctx.run_id,
                    node_id=node.id,
                    node_type=node.type,
                    option_key="smiles",
                )
            ) from exc
        if matches:
            keep.append(index)
    out_dir = node_dir(ctx, node)
    artifacts = []
    kept_contents = []
    for new_index, old_index in enumerate(keep, start=1):
        content = contents[old_index]
        kept_contents.append(content)
        artifacts.append(await ctx.write_text_artifact(node, out_dir / f"complex_{new_index:04d}.pdb", content, "Batch Protein (With Ligand)", "chemical/x-pdb"))
    result = {"complexes": payload_from_artifacts("Batch Protein (With Ligand)", artifacts, data=kept_contents)}
    if scores is not None:
        kept_scores = [scores.data[index] for index in keep]
        json_artifact = await ctx.write_json_artifact(node, out_dir / "scores.json", kept_scores, "Score", item_count=len(kept_scores))
        csv_artifact = await ctx.write_csv_artifact(node, out_dir / "scores.csv", scores_to_rows(kept_scores), "Score")
        result["score"] = payload_from_artifacts("Score", [json_artifact, csv_artifact], data=kept_scores, item_count=len(kept_scores))
    return result


def _chirality_smiles(ctx: ExecutionContext, node: WorkflowNode) -> str:
    smiles = str(option(node, "smiles", "") or "").strip()
    if not smiles:
        raise BackendError(
            make_error(
                "MISSING_CHIRALITY_SMILES",
                "FilterChirality requires a standard SMILES option with stereochemistry.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                option_key="smiles",
            )
        )
    return smiles
