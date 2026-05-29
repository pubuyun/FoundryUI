from backend.bio.fasta import parse_fasta, write_fasta
from backend.nodes.common import node_dir
from backend.nodes.registry import FoundryNode
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload


class MpnnNode(FoundryNode):
    category = "MPNN"

    @staticmethod
    async def collect_fasta(ctx, node, paths, error_code: str) -> dict[str, TypedPayload]:
        if not paths:
            raise BackendError(make_error(error_code, f"{node.type} did not produce FASTA outputs.", run_id=ctx.run_id, node_id=node.id, node_type=node.type))
        records = []
        for path in paths:
            records.extend(parse_fasta(path.read_text()))
        data = [{"id": record.id, "sequence": record.sequence, "description": record.description} for record in records]
        artifact = await ctx.write_text_artifact(node, node_dir(ctx, node) / "sequences.fasta", write_fasta(data), "Batch Sequence", "text/x-fasta", item_count=len(data))
        return {"sequences": TypedPayload(type_name="Batch Sequence", item_count=len(data), artifact_ids=[artifact.artifact_id], paths=[artifact.path], data=data)}
