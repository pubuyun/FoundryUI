import asyncio

from backend.nodes.common import node_dir, option, payload_from_artifacts, read_payload_files, scores_to_rows
from backend.nodes.filter.base import FilterNode
from backend.schemas.errors import BackendError, make_error
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class FilterByScore(FilterNode):
    type_name = "FilterByScore"
    title = "Filter By Score"
    description = "Filter model batches by one score metric, preserving score ordering."
    inputs = (P("structures", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"), P("score", "Score", label="Score"))
    options = (O("metric", "select", "", label="Choose score field when run reaches this node"), O("mode", "select", "Is largest top", choices=("Is largest top", "Is smallest top", "Greater than", "Smaller than", "Higher than", "Lower than"), label="Filter Mode"), O("threshold", "float", 10, label="top / threshold"))
    outputs = (P("structures", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"), P("score", "Score", label="Score"))
    ui = {"manual": True, "viewerMode": "score", "selectorFields": {"score": "metric"}, "blinkWhenPending": True}
    catalog_order = 160

    @classmethod
    async def execute(cls, ctx, node, inputs):
        structures = inputs["structures"]
        score_payload = inputs["score"]
        cls.ensure_score_alignment(ctx, node, structures, score_payload, ["structures", "score"])
        scores = cls.score_list(score_payload.data)
        metric = await cls.runtime_score_metric(ctx, node, score_payload)
        mode = str(option(node, "mode", "Is largest top"))
        threshold = float(option(node, "threshold", 10))

        indexed = list(enumerate(scores))
        if mode == "Is largest top":
            keep = {index for index, _ in sorted(indexed, key=lambda item: cls.score_value(item[1], metric, float("-inf")), reverse=True)[: int(threshold)]}
        elif mode == "Is smallest top":
            keep = {index for index, _ in sorted(indexed, key=lambda item: cls.score_value(item[1], metric, float("inf")))[: int(threshold)]}
        elif mode in {"Higher than", "Greater than"}:
            keep = {index for index, score in indexed if cls.score_value(score, metric, float("-inf")) > threshold}
        else:
            keep = {index for index, score in indexed if cls.score_value(score, metric, float("inf")) < threshold}

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

    @staticmethod
    def score_value(score: dict, metric: str, default: float) -> float:
        value = score.get(metric, default)
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    async def runtime_score_metric(cls, ctx, node, score_payload):
        fields = cls.numeric_score_fields(cls.score_list(score_payload.data))
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

    @staticmethod
    def numeric_score_fields(scores: list[dict]) -> list[str]:
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

    @staticmethod
    def score_list(data) -> list[dict]:
        if isinstance(data, dict) and isinstance(data.get("scores"), list):
            return [item for item in data["scores"] if isinstance(item, dict)]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []
