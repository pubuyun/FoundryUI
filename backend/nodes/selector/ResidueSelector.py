from backend.nodes.common import node_dir, option, payload_from_artifacts, split_selector
from backend.nodes.selector.base import SelectorNode
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class ResidueSelector(SelectorNode):
    type_name = "ResidueSelector"
    title = "Residue Selector"
    description = 'Use a node-local 3D viewer or type residue ids such as "A103,A201".'
    inputs = (P("protein", "Protein", optional=True, label="Protein"),)
    options = (O("residues", "text", "", label="Select manually when run reaches this node"), O("viewer", "viewer", "Open", label="3D Viewer residue selector", viewer_mode="residue"))
    outputs = (P("residues", "List of Residues", label="List of Residues"),)
    ui = {"manual": True, "viewerMode": "residue", "selectorFields": {"residue": "residues"}, "structureSource": "connectedSourceOutput", "blinkWhenPending": True}
    catalog_order = 20

    @classmethod
    async def execute(cls, ctx, node, inputs):
        values = await cls.runtime_selector_values(ctx, node, inputs, "residues") if inputs else {}
        residues = split_selector(values.get("residues", option(node, "residues", "")))
        if inputs and residues:
            cls.validate_residues_exist(ctx, node, inputs, residues, "residues")
        artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "residues.json", residues, "List of Residues", item_count=len(residues))
        return {"residues": payload_from_artifacts("List of Residues", [artifact], data=residues)}
