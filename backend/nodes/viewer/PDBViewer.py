from backend.nodes.viewer.base import ViewerNode
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class PDBViewer(ViewerNode):
    type_name = "PDBViewer"
    title = "PDB Viewer"
    description = "Inspect batch protein or protein-ligand structures in a node-local 3D viewer."
    inputs = (P("structures", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"),)
    options = (O("viewer", "viewer", "Open", label="File Selector + 3D Viewer", viewer_mode="batchStructure"),)
    ui = {"viewerMode": "batchStructure", "structureSource": "selfOutputOrConnectedSource"}
    catalog_order = 250

    @classmethod
    async def execute(cls, ctx, node, inputs):
        return {}
