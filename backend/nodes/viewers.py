from __future__ import annotations

from backend.nodes.common import ExecutionContext
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def pdb_viewer(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    return {}


async def sequence_viewer(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    return {}
