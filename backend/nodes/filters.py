from __future__ import annotations

import re

from backend.bio.ligand import ligand_has_chirality_targets
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
    targets = _chirality_targets(ctx, node)
    keep = []
    for index, content in enumerate(contents):
        _, complex_ligand = split_pdb_complex(content)
        if ligand_has_chirality_targets(complex_ligand, targets):
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


def _chirality_targets(ctx: ExecutionContext, node: WorkflowNode) -> list[tuple[str, str]]:
    raw = option(node, "targets", "")
    if raw in (None, ""):
        return []
    if isinstance(raw, list):
        return [_target_from_item(ctx, node, item) for item in raw]
    entries = [entry.strip() for entry in re.split(r"[,;\n]+", str(raw)) if entry.strip()]
    return [_target_from_text(ctx, node, entry) for entry in entries]


def _target_from_item(ctx: ExecutionContext, node: WorkflowNode, item) -> tuple[str, str]:
    if isinstance(item, dict):
        atom = str(item.get("atom") or item.get("atomName") or item.get("name") or "").strip()
        chirality = str(item.get("chirality") or item.get("cip") or "").strip().upper()
        return _validate_target(ctx, node, atom, chirality, item)
    if isinstance(item, (list, tuple)) and len(item) == 2:
        return _validate_target(ctx, node, str(item[0]).strip(), str(item[1]).strip().upper(), item)
    return _target_from_text(ctx, node, str(item))


def _target_from_text(ctx: ExecutionContext, node: WorkflowNode, text: str) -> tuple[str, str]:
    parts = [part for part in re.split(r"[:=\s]+", text.strip()) if part]
    if len(parts) != 2:
        raise BackendError(
            make_error(
                "INVALID_CHIRALITY_TARGET",
                "FilterChirality target entries must be atom/chirality pairs like C0:S.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                option_key="targets",
                details={"entry": text},
            )
        )
    return _validate_target(ctx, node, parts[0], parts[1].upper(), text)


def _validate_target(ctx: ExecutionContext, node: WorkflowNode, atom_name: str, chirality: str, source) -> tuple[str, str]:
    if not atom_name or chirality not in {"R", "S"}:
        raise BackendError(
            make_error(
                "INVALID_CHIRALITY_TARGET",
                "FilterChirality target entries must include an atom name and chirality R or S.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                option_key="targets",
                details={"entry": source},
            )
        )
    return atom_name, chirality
