from backend.nodes.viewer.base import ViewerNode
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class SequenceViewer(ViewerNode):
    type_name = "SequenceViewer"
    title = "Sequence Viewer"
    description = "Inspect batch sequences from FASTA or generated designs."
    inputs = (P("sequences", "Batch Sequence", label="Batch Sequence"),)
    options = (O("file", "text", "", label="File Selector", frontend_default="sequence_0001.fasta"),)
    catalog_order = 260

    @classmethod
    async def execute(cls, ctx, node, inputs):
        return {}
