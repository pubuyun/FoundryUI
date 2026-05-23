from __future__ import annotations

from backend.schemas.workflow import WorkflowGraph


def build_ryvencore_plan(graph: WorkflowGraph) -> WorkflowGraph:
    """Placeholder adapter boundary for Ryvencore integration.

    The API and validators use FoundryUI's normalized graph contract. This
    function keeps the execution seam explicit so Ryvencore-specific details do
    not leak into request/response schemas while the node runtime matures.
    """

    return graph
