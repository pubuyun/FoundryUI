from backend.nodes.common import node_dir, payload_from_artifacts, scores_to_rows
from backend.nodes.registry import FoundryNode


class ScoringNode(FoundryNode):
    category = "Analysis"

    @staticmethod
    async def score_output(ctx, node, scores: list[dict[str, float]]):
        out_dir = node_dir(ctx, node)
        json_artifact = await ctx.write_json_artifact(node, out_dir / "scores.json", scores, "Score", item_count=len(scores))
        csv_artifact = await ctx.write_csv_artifact(node, out_dir / "scores.csv", scores_to_rows(scores), "Score")
        return {"score": payload_from_artifacts("Score", [json_artifact, csv_artifact], data=scores, metadata={"score_count": len(scores)}, item_count=len(scores))}
