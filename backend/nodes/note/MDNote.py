from backend.nodes.registry import FoundryNode
from backend.workflow.catalog import OptionSpec as O


class MDNote(FoundryNode):
    type_name = "MDNote"
    title = "MD Note"
    category = "Note"
    description = "Free-form workflow note. No data ports."
    options = (O("note", "textarea", "", label="Text Field", frontend_default="Design notes"),)
    terminal = True
    catalog_order = 10

    @classmethod
    async def execute(cls, ctx, node, inputs):
        return {}

