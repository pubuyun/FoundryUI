from backend.nodes.common import node_dir, option, payload_from_artifacts, read_payload_files, scores_to_rows
from backend.nodes.logic.base import LogicNode
from backend.schemas.errors import BackendError, make_error
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class BinaryLogic(LogicNode):
    type_name = "BinaryLogic"
    title = "Binary Logic"
    description = "Logical operations across two same-type model batches with optional scores."
    inputs = (P("structures1", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand) 1"), P("score1", "Score", optional=True, label="Score1"), P("structures2", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand) 2"), P("score2", "Score", optional=True, label="Score2"))
    options = (O("operation", "select", "OR", choices=("OR", "AND", "NOR", "NAND", "XOR"), label="Operation"),)
    outputs = (P("structures", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"), P("score", "Score", label="Score"))
    catalog_order = 210

    @classmethod
    async def execute(cls, ctx, node, inputs):
        left = inputs["structures1"]
        right = inputs["structures2"]
        left_type = left.metadata.get("effective_type", left.type_name)
        right_type = right.metadata.get("effective_type", right.type_name)
        if left_type != right_type and "Batch Structure" not in {left_type, right_type}:
            raise BackendError(make_error("INCOMPATIBLE_STRUCTURE_TYPES", "BinaryLogic structure inputs must be the same effective type.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, details={"left_type": left_type, "right_type": right_type}))
        if "score1" in inputs:
            cls.ensure_score_alignment(ctx, node, left, inputs["score1"], ["structures1", "score1"])
        if "score2" in inputs:
            cls.ensure_score_alignment(ctx, node, right, inputs["score2"], ["structures2", "score2"])

        left_contents = read_payload_files(ctx, left)
        right_contents = read_payload_files(ctx, right)
        left_set = {content: index for index, content in enumerate(left_contents)}
        right_set = {content: index for index, content in enumerate(right_contents)}
        operation = str(option(node, "operation", "OR"))
        if operation == "AND":
            selected = [content for content in left_contents if content in right_set]
        elif operation == "XOR":
            selected = [content for content in [*left_contents, *right_contents] if (content in left_set) ^ (content in right_set)]
        elif operation == "NOR":
            selected = []
        elif operation == "NAND":
            selected = [content for content in [*left_contents, *right_contents] if content not in left_set or content not in right_set]
        else:
            selected = list(dict.fromkeys([*left_contents, *right_contents]))

        out_dir = node_dir(ctx, node)
        artifacts = []
        for index, content in enumerate(selected, start=1):
            artifacts.append(await ctx.write_text_artifact(node, out_dir / f"structure_{index:04d}.pdb", content, left_type, "chemical/x-pdb"))

        result = {"structures": payload_from_artifacts(left.type_name, artifacts, data=selected, metadata={"effective_type": left_type})}
        if "score1" in inputs:
            score_map = {content: inputs["score1"].data[index] for index, content in enumerate(left_contents)}
            if "score2" in inputs:
                score_map.update({content: inputs["score2"].data[index] for index, content in enumerate(right_contents)})
            scores = [score_map[content] for content in selected if content in score_map]
            if len(scores) == len(selected):
                json_artifact = await ctx.write_json_artifact(node, out_dir / "scores.json", scores, "Score", item_count=len(scores))
                csv_artifact = await ctx.write_csv_artifact(node, out_dir / "scores.csv", scores_to_rows(scores), "Score")
                result["score"] = payload_from_artifacts("Score", [json_artifact, csv_artifact], data=scores, item_count=len(scores))
        return result
