from pathlib import Path

from backend.bio.pdb import validate_pdb
from backend.nodes.common import embedded_or_stored_uploads, node_dir, payload_from_artifacts
from backend.nodes.input.base import InputNode
from backend.nodes.registry import UploadValidation
from backend.schemas.errors import BackendError, make_error
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class ProteinInput(InputNode):
    type_name = "ProteinInput"
    title = "Protein Input"
    description = "Manual batch protein input from PDB files."
    options = (O("file", "file", "", label="Upload File", accept=".pdb"), O("viewer", "viewer", "Open", label="File Selector + 3D Viewer", viewer_mode="batchStructure"))
    outputs = (P("batchProtein", "Batch Protein", label="Batch Protein"),)
    upload_validation = UploadValidation({"pdb"}, "ProteinInput requires uploaded PDB content or upload file ids.", "MISSING_PROTEIN_FILE", "INVALID_PROTEIN_FILE")
    catalog_order = 70

    @classmethod
    async def execute(cls, ctx, node, inputs):
        uploads = embedded_or_stored_uploads(ctx, node)
        if not uploads:
            raise BackendError(make_error("MISSING_PROTEIN_FILE", "ProteinInput requires uploaded PDB files.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file"))
        out_dir = node_dir(ctx, node)
        artifacts = []
        pdbs: list[str] = []
        for index, (name, file_type, content) in enumerate(uploads, start=1):
            if (file_type or Path(name).suffix.lower().lstrip(".")).lower() != "pdb":
                raise BackendError(make_error("INVALID_PROTEIN_FILE_TYPE", "ProteinInput accepts PDB files.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file", details={"file": name}))
            validate_pdb(content)
            artifact = await ctx.write_text_artifact(node, out_dir / f"protein_{index:04d}.pdb", content, "Batch Protein", "chemical/x-pdb")
            artifacts.append(artifact)
            pdbs.append(content)
        return {"batchProtein": payload_from_artifacts("Batch Protein", artifacts, data=pdbs)}
