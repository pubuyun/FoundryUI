from __future__ import annotations

import asyncio

from backend.nodes.common import ExecutionContext, node_dir, option, payload_from_artifacts, split_selector
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def atom_selector(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    values = await _runtime_selector_values(ctx, node, inputs, "atoms") if inputs else {}
    atoms = split_selector(values.get("atoms", option(node, "atoms", "")))
    artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "atoms.json", atoms, "List of Atoms", item_count=len(atoms))
    return {"atoms": payload_from_artifacts("List of Atoms", [artifact], data=atoms)}


async def residue_selector(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    values = await _runtime_selector_values(ctx, node, inputs, "residues") if inputs else {}
    residues = split_selector(values.get("residues", option(node, "residues", "")))
    artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "residues.json", residues, "List of Residues", item_count=len(residues))
    return {"residues": payload_from_artifacts("List of Residues", [artifact], data=residues)}


async def _runtime_selector_values(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload], field: str) -> dict:
    payloads = {
        key: {
            "type_name": payload.type_name,
            "item_count": payload.item_count,
            "artifact_ids": payload.artifact_ids,
            "paths": payload.paths,
            "metadata": payload.metadata,
        }
        for key, payload in inputs.items()
    }
    try:
        return await ctx.registry.request_node_input(
            ctx.run_id,
            node.id,
            node.type,
            [field],
            payloads,
            {field: option(node, field, "")},
        )
    except asyncio.CancelledError as exc:
        raise BackendError(
            make_error(
                "RUN_CANCELLED",
                "Run was stopped while waiting for selector input.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                recoverable=True,
            )
        ) from exc
