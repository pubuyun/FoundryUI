from pathlib import Path

from backend.bio.ligand import standardize_ligand_pdb
from backend.bio.pdb import first_residue_name, rename_residue, validate_pdb
from backend.nodes.common import embedded_or_stored_uploads, node_dir, payload_from_artifacts
from backend.nodes.input.base import InputNode
from backend.nodes.registry import UploadValidation
from backend.schemas.errors import BackendError, make_error
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class LigandInput(InputNode):
    type_name = "LigandInput"
    title = "Ligand Input"
    description = "Manual ligand input from PDB upload."
    options = (O("file", "file", "", label="Upload File", accept=".pdb"), O("viewer", "viewer", "Open", label="3D Viewer", viewer_mode="structure"))
    outputs = (P("ligand", "Ligand", label="Ligand"),)
    upload_validation = UploadValidation({"pdb"}, "LigandInput requires uploaded PDB content or upload file ids.", "MISSING_LIGAND_FILE", "INVALID_LIGAND_FILE")
    catalog_order = 60

    @classmethod
    async def execute(cls, ctx, node, inputs):
        out_dir = node_dir(ctx, node)
        uploads = embedded_or_stored_uploads(ctx, node)
        if not uploads:
            raise BackendError(make_error("MISSING_LIGAND_FILE", "LigandInput requires an uploaded PDB file.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file"))
        pdbs: list[str] = []
        for name, file_type, content in uploads:
            detected = (file_type or Path(name).suffix.lower().lstrip(".")).lower()
            if detected != "pdb":
                raise BackendError(make_error("INVALID_LIGAND_FILE_TYPE", "LigandInput accepts PDB files.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="file", details={"file": name}))
            validate_pdb(content)
            pdbs.append(content)
        if len(pdbs) == 1:
            residue_name = ctx.next_ligand_residue_name()
            pdb, smiles = standardize_ligand_pdb(rename_residue(pdbs[0], residue_name), residue_name)
            artifact = await ctx.write_text_artifact(node, out_dir / "ligand.pdb", pdb, "Ligand", "chemical/x-pdb")
            return {"ligand": payload_from_artifacts("Ligand", [artifact], data=pdb, metadata={"residue_name": residue_name, "residue_names": [residue_name], "smiles": smiles, "smiles_list": [smiles], "renamed_residue": True, "standardized": True})}

        artifacts = []
        residue_names = [first_residue_name(pdb) for pdb in pdbs]
        standardized_pdbs = []
        smiles_values = []
        for index, pdb in enumerate(pdbs, start=1):
            standardized, smiles = standardize_ligand_pdb(pdb)
            standardized_pdbs.append(standardized)
            smiles_values.append(smiles)
            artifact = await ctx.write_text_artifact(node, out_dir / f"ligand_{index:04d}.pdb", standardized, "Batch Ligand", "chemical/x-pdb")
            artifacts.append(artifact)
        return {"ligand": payload_from_artifacts("Batch Ligand", artifacts, data=standardized_pdbs, metadata={"residue_names": residue_names, "smiles_list": smiles_values, "renamed_residue": False, "standardized": True})}
