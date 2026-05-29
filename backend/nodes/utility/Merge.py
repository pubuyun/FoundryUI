from backend.bio.pdb import merge_pdb_structures
from backend.nodes.common import node_dir, payload_from_artifacts, read_payload_files
from backend.nodes.utility.base import UtilityNode
from backend.schemas.errors import BackendError, make_error
from backend.workflow.catalog import PortSpec as P


class Merge(UtilityNode):
    type_name = "Merge"
    title = "Merge"
    description = "Merge two Load into chain-separated structures."
    inputs = (P("inputA", "Batch Protein (With Ligand)", label="Input A"), P("inputB", "Batch Protein (With Ligand)", label="Input B"))
    outputs = (P("complexes", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"),)
    catalog_order = 230

    @classmethod
    async def execute(cls, ctx, node, inputs):
        left_payload = inputs.get("inputA") or inputs.get("batchProtein")
        right_payload = inputs.get("inputB") or inputs.get("ligand")
        if left_payload is None or right_payload is None:
            raise BackendError(make_error("MISSING_MERGE_INPUT", "Merge requires two connected inputs.", run_id=ctx.run_id, node_id=node.id, node_type=node.type))
        left_items = read_payload_files(ctx, left_payload)
        right_items = read_payload_files(ctx, right_payload)
        count = cls.merged_count(left_payload, right_payload, node, ctx.run_id)
        out_dir = node_dir(ctx, node)
        artifacts = []
        complexes = []
        output_type = "Batch Protein" if cls.protein_only(left_payload) and cls.protein_only(right_payload) else "Batch Protein (With Ligand)"
        for index in range(count):
            left = left_items[0 if left_payload.item_count <= 1 else index]
            right = right_items[0 if right_payload.item_count <= 1 else index]
            complex_pdb = merge_pdb_structures([left, right])
            artifact = await ctx.write_text_artifact(node, out_dir / f"merged_{index + 1:04d}.pdb", complex_pdb, output_type, "chemical/x-pdb")
            artifacts.append(artifact)
            complexes.append(complex_pdb)
        return {"complexes": payload_from_artifacts(output_type, artifacts, data=complexes)}

    @staticmethod
    def merged_count(left, right, node, run_id: str) -> int:
        left_count = max(left.item_count or len(left.paths) or 1, 1)
        right_count = max(right.item_count or len(right.paths) or 1, 1)
        if left_count == right_count:
            return left_count
        if left_count == 1:
            return right_count
        if right_count == 1:
            return left_count
        raise BackendError(make_error("MERGE_LENGTH_MISMATCH", "Merge inputs must have the same item count unless one input is single.", run_id=run_id, node_id=node.id, node_type=node.type, details={"left_count": left_count, "right_count": right_count}))

    @staticmethod
    def protein_only(payload) -> bool:
        return payload.type_name in {"Protein", "Batch Protein"}
