from pathlib import Path

from backend.bio.fasta import parse_fasta, write_fasta
from backend.nodes.common import embedded_or_stored_uploads, node_dir, payload_from_artifacts
from backend.nodes.input.base import InputNode
from backend.nodes.registry import UploadValidation
from backend.schemas.errors import BackendError, make_error
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class SequenceInput(InputNode):
    type_name = "SequenceInput"
    title = "Sequence Input"
    description = "Manual batch sequence input from FASTA files."
    options = (O("file", "file", "", label="Upload File", accept=".fasta,.fa"),)
    outputs = (P("batchSequence", "Batch Sequence", label="Batch Sequence"),)
    upload_validation = UploadValidation({"fasta", "fa"}, "SequenceInput requires uploaded FASTA content or upload file ids.", "MISSING_FASTA_FILE", "INVALID_FASTA_FILE")
    catalog_order = 90

    @classmethod
    async def execute(cls, ctx, node, inputs):
        uploads = embedded_or_stored_uploads(ctx, node)
        if not uploads:
            raise BackendError(make_error("MISSING_FASTA_FILE", "SequenceInput requires uploaded FASTA files.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file"))
        records = []
        for name, file_type, content in uploads:
            if (file_type or Path(name).suffix.lower().lstrip(".")).lower() not in {"fasta", "fa"}:
                raise BackendError(make_error("INVALID_FASTA_FILE_TYPE", "SequenceInput accepts FASTA files.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file", details={"file": name}))
            records.extend(parse_fasta(content))
        data = [{"id": record.id, "sequence": record.sequence, "description": record.description} for record in records]
        artifact = await ctx.write_text_artifact(node, node_dir(ctx, node) / "sequences.fasta", write_fasta(data), "Batch Sequence", "text/x-fasta", item_count=len(data))
        return {"batchSequence": payload_from_artifacts("Batch Sequence", [artifact], data=data, metadata={"sequence_count": len(data)})}
