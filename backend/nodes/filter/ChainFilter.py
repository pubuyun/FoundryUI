from backend.bio.pdb import filter_pdb_chains
from backend.nodes.common import node_dir, option, payload_from_artifacts, read_payload_files, split_selector
from backend.nodes.filter.base import FilterNode
from backend.nodes.selector.base import SelectorNode
from backend.schemas.errors import BackendError, make_error
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class ChainFilter(FilterNode):
    type_name = "ChainFilter"
    title = "Chain Filter"
    description = "Pause at runtime and keep selected protein chains."
    inputs = (P("batchProtein", "Batch Protein", label="Batch Protein"),)
    options = (O("chains", "text", "", label="Select manually when run reaches this node"), O("viewer", "viewer", "Open", label="3D Viewer chain selector", viewer_mode="chain"))
    outputs = (P("batchProtein", "Batch Protein", label="Batch Protein"),)
    ui = {"manual": True, "viewerMode": "chain", "selectorFields": {"chain": "chains"}, "structureSource": "selfOutputOrConnectedSource", "blinkWhenPending": True}
    catalog_order = 50

    @classmethod
    async def execute(cls, ctx, node, inputs):
        values = await SelectorNode.runtime_selector_values(ctx, node, inputs, "chains")
        chains = split_selector(values.get("chains", option(node, "chains", "")))
        if not chains:
            raise BackendError(make_error("MISSING_CHAIN_SELECTION", "ProteinChainSelector requires at least one selected chain.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="chains"))
        proteins = read_payload_files(ctx, inputs["batchProtein"])
        SelectorNode.validate_chains_exist(ctx, node, proteins, chains)
        out_dir = node_dir(ctx, node)
        artifacts = []
        filtered = []
        for index, protein in enumerate(proteins, start=1):
            content = filter_pdb_chains(protein, chains)
            artifact = await ctx.write_text_artifact(node, out_dir / f"protein_{index:04d}.pdb", content, "Batch Protein", "chemical/x-pdb")
            artifacts.append(artifact)
            filtered.append(content)
        return {"batchProtein": payload_from_artifacts("Batch Protein", artifacts, data=filtered)}
