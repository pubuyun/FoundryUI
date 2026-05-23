from __future__ import annotations

from backend.nodes.common import ExecutionContext, node_dir, option, payload_from_artifacts, split_selector
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def atom_selector(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    atoms = split_selector(option(node, "atoms", ""))
    artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "atoms.json", atoms, "List of Atoms", item_count=len(atoms))
    return {"atoms": payload_from_artifacts("List of Atoms", [artifact], data=atoms)}


async def residue_selector(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    residues = split_selector(option(node, "residues", ""))
    artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "residues.json", residues, "List of Residues", item_count=len(residues))
    return {"residues": payload_from_artifacts("List of Residues", [artifact], data=residues)}
