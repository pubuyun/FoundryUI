from backend.bio.pdb import filter_pdb_residues
from backend.nodes.common import node_dir, option, payload_from_artifacts, read_payload_files
from backend.schemas.errors import BackendError, make_error
from backend.nodes.selector.base import SelectorNode
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class ResidueAtomSelector(SelectorNode):
    type_name = "ResidueAtomSelector"
    title = "Residue Atom Selector"
    description = "Pause at runtime and select protein atoms from selected residues."
    inputs = (P("residues", "List of Residues", label="List of Residues"), P("protein", "Protein", label="Protein"))
    options = (O("proteinAtoms", "textarea", "", label="Select manually when run reaches this node"), O("viewer", "viewer", "Open", label="3D Viewer protein atom selector", viewer_mode="proteinAtom"))
    outputs = (P("proteinAtoms", "Residues Atoms List", label="Residues Atoms List"),)
    ui = {"manual": True, "viewerMode": "proteinAtom", "selectorFields": {"proteinAtom": "proteinAtoms"}, "structureSource": "connectedSourceOutput", "blinkWhenPending": True}
    catalog_order = 40

    @classmethod
    async def execute(cls, ctx, node, inputs):
        residues = cls.residue_values(inputs.get("residues"))
        protein = inputs.get("protein")
        if protein is None:
            raise BackendError(make_error("MISSING_PROTEIN_INPUT", "ProteinAtomSelector requires a protein input.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, interface_key="protein"))

        request_inputs = {}
        protein_files = read_payload_files(ctx, protein)
        if protein_files and residues:
            cls.validate_residues_in_contents(ctx, node, protein_files, residues, "residues")
            selected_pdb = filter_pdb_residues(protein_files[0], residues)
            preview = await ctx.write_text_artifact(node, node_dir(ctx, node) / "selected_residues_for_atom_selection.pdb", selected_pdb, "Protein", media_type="chemical/x-pdb")
            request_inputs["selectedResidues"] = payload_from_artifacts("Protein", [preview], data=selected_pdb)
        else:
            request_inputs["protein"] = protein

        values = await cls.runtime_selector_values(ctx, node, request_inputs, "proteinAtoms")
        atoms = cls.parse_protein_atom_map(ctx, node, values.get("proteinAtoms", option(node, "proteinAtoms", "")))
        if atoms:
            cls.validate_protein_atoms_exist(ctx, node, protein_files, atoms)
        artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "residue_atoms.json", atoms, "Residues Atoms List", item_count=len(atoms))
        return {"proteinAtoms": payload_from_artifacts("Residues Atoms List", [artifact], data=atoms, item_count=len(atoms))}
