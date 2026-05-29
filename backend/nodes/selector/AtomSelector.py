from backend.nodes.common import node_dir, option, payload_from_artifacts, split_selector
from backend.nodes.selector.base import SelectorNode
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class AtomSelector(SelectorNode):
    type_name = "AtomSelector"
    title = "Atom Selector"
    description = 'Use a node-local 3D viewer or type atom ids such as "C1,C2".'
    inputs = (P("ligand", "Ligand", optional=True, label="Ligand"),)
    options = (O("atoms", "text", "", label="Select manually when run reaches this node"), O("viewer", "viewer", "Open", label="3D Viewer atom selector", viewer_mode="atom"))
    outputs = (P("atoms", "List of Atoms", label="List of Atoms"),)
    ui = {"manual": True, "viewerMode": "atom", "selectorFields": {"atom": "atoms"}, "structureSource": "connectedSourceOutput", "blinkWhenPending": True}
    catalog_order = 30

    @classmethod
    async def execute(cls, ctx, node, inputs):
        values = await cls.runtime_selector_values(ctx, node, inputs, "atoms") if inputs else {}
        atoms = split_selector(values.get("atoms", option(node, "atoms", "")))
        if inputs and atoms:
            cls.validate_atoms_exist(ctx, node, inputs, atoms, "atoms")
        artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "atoms.json", atoms, "List of Atoms", item_count=len(atoms))
        return {"atoms": payload_from_artifacts("List of Atoms", [artifact], data=atoms)}
