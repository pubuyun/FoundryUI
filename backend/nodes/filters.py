from __future__ import annotations

import asyncio
import re

from backend.bio.ligand import ligand_has_atom_chirality_targets, ligand_matches_smiles_chirality
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
    scores = _score_list(score_payload.data)
    metric = await _runtime_score_metric(ctx, node, score_payload)
    mode = str(option(node, "mode", "Is largest top"))
    threshold = float(option(node, "threshold", 10))

    indexed = list(enumerate(scores))
    if mode == "Is largest top":
        keep = {index for index, _ in sorted(indexed, key=lambda item: _score_value(item[1], metric, float("-inf")), reverse=True)[: int(threshold)]}
    elif mode == "Is smallest top":
        keep = {index for index, _ in sorted(indexed, key=lambda item: _score_value(item[1], metric, float("inf")))[: int(threshold)]}
    elif mode in {"Higher than", "Greater than"}:
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


async def _runtime_score_metric(ctx: ExecutionContext, node: WorkflowNode, score_payload: TypedPayload) -> str:
    fields = _numeric_score_fields(_score_list(score_payload.data))
    if not fields:
        raise BackendError(
            make_error(
                "NO_NUMERIC_SCORE_FIELDS",
                "FilterByScore requires at least one numeric score property.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                interface_key="score",
            )
        )
    default = str(option(node, "metric", fields[0]) or fields[0])
    if default not in fields:
        default = fields[0]
    try:
        values = await ctx.registry.request_node_input(
            ctx.run_id,
            node.id,
            node.type,
            ["metric"],
            {
                "score": {
                    "type_name": score_payload.type_name,
                    "item_count": score_payload.item_count,
                    "artifact_ids": score_payload.artifact_ids,
                    "paths": score_payload.paths,
                    "metadata": {**score_payload.metadata, "score_fields": fields},
                }
            },
            {"metric": default},
            choices={"metric": fields},
        )
    except asyncio.CancelledError as exc:
        raise BackendError(
            make_error(
                "RUN_CANCELLED",
                "Run was stopped while waiting for score filter input.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                recoverable=True,
            )
        ) from exc
    metric = str(values.get("metric") or default)
    if metric not in fields:
        raise BackendError(make_error("INVALID_SCORE_FIELD", "Selected score field is not present as a numeric property.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="metric", details={"metric": metric, "score_fields": fields}))
    return metric


def _numeric_score_fields(scores: list[dict]) -> list[str]:
    fields: list[str] = []
    for score in scores:
        if not isinstance(score, dict):
            continue
        for key, value in score.items():
            if key in fields:
                continue
            try:
                float(value)
            except (TypeError, ValueError):
                continue
            fields.append(str(key))
    return fields


def _score_list(data) -> list[dict]:
    if isinstance(data, dict) and isinstance(data.get("scores"), list):
        return [item for item in data["scores"] if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


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


async def filter_atoms_chirality(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    complexes = inputs["complexes"]
    scores = inputs.get("score")
    if scores is not None:
        ensure_score_alignment(ctx, node, complexes, scores, ["complexes", "score"])
    contents = read_payload_files(ctx, complexes)
    targets = await _runtime_atom_chirality_targets(ctx, node, complexes)
    keep = []
    for index, content in enumerate(contents):
        _, complex_ligand = split_pdb_complex(content)
        if ligand_has_atom_chirality_targets(complex_ligand, targets):
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


async def _runtime_atom_chirality_targets(ctx: ExecutionContext, node: WorkflowNode, complexes: TypedPayload) -> list[tuple[str, str]]:
    first_ligand_artifact = None
    if complexes.paths:
        first_complex = ctx.store.absolute(ctx.run_id, complexes.paths[0]).read_text()
        _, first_ligand = split_pdb_complex(first_complex)
        first_ligand_artifact = await ctx.write_text_artifact(node, node_dir(ctx, node) / "first_ligand_for_chirality.pdb", first_ligand, "Ligand", "chemical/x-pdb")
    payloads = {}
    if first_ligand_artifact is not None:
        payloads["ligand"] = {
            "type_name": "Ligand",
            "item_count": 1,
            "artifact_ids": [first_ligand_artifact.artifact_id],
            "paths": [first_ligand_artifact.path],
            "metadata": {"source": "first_complex"},
        }
    payloads["complexes"] = {
        "type_name": complexes.type_name,
        "item_count": complexes.item_count,
        "artifact_ids": complexes.artifact_ids[:1],
        "paths": complexes.paths[:1],
        "metadata": complexes.metadata,
    }
    try:
        values = await ctx.registry.request_node_input(
            ctx.run_id,
            node.id,
            node.type,
            ["chiralityTargets"],
            payloads,
            {"chiralityTargets": option(node, "chiralityTargets", "")},
        )
    except asyncio.CancelledError as exc:
        raise BackendError(
            make_error(
                "RUN_CANCELLED",
                "Run was stopped while waiting for chirality input.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                recoverable=True,
            )
        ) from exc
    targets = _atom_chirality_targets(ctx, node, values.get("chiralityTargets", option(node, "chiralityTargets", "")))
    if not targets:
        raise BackendError(
            make_error(
                "MISSING_ATOM_CHIRALITY_TARGETS",
                "FilterAtomsChirality requires at least one atom/chirality target.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                option_key="chiralityTargets",
            )
        )
    return targets


def _atom_chirality_targets(ctx: ExecutionContext, node: WorkflowNode, raw) -> list[tuple[str, str]]:
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
                "INVALID_ATOM_CHIRALITY_TARGET",
                "FilterAtomsChirality target entries must be atom/chirality pairs like C1:S.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                option_key="chiralityTargets",
                details={"entry": text},
            )
        )
    return _validate_target(ctx, node, parts[0], parts[1].upper(), text)


def _validate_target(ctx: ExecutionContext, node: WorkflowNode, atom_name: str, chirality: str, source) -> tuple[str, str]:
    if not atom_name or chirality not in {"R", "S"}:
        raise BackendError(
            make_error(
                "INVALID_ATOM_CHIRALITY_TARGET",
                "FilterAtomsChirality target entries must include an atom name and chirality R or S.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                option_key="chiralityTargets",
                details={"entry": source},
            )
        )
    return atom_name, chirality
