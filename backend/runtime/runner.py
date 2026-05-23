from __future__ import annotations

import traceback

from backend.artifacts.registry import artifact_store
from backend.nodes.common import ExecutionContext
from backend.nodes.dispatch import HANDLERS
from backend.runtime.registry import run_registry
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import RunCreateRequest, WorkflowGraph, WorkflowNode
from backend.workflow.catalog import spec_for
from backend.workflow.graph import inbound_connections, topological_order
from backend.workflow.ryvencore_adapter import build_ryvencore_plan
from backend.workflow.type_conversions import convert_payload
from backend.workflow.validation import validate_workflow


async def run_workflow(run_id: str, request: RunCreateRequest) -> None:
    graph = build_ryvencore_plan(request.workflow_graph())
    errors = validate_workflow(graph)
    if errors:
        for error in errors:
            error.run_id = run_id
            await run_registry.add_error(run_id, error)
        return

    ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads=request.embedded_uploads())
    outputs: dict[tuple[str, str], TypedPayload] = {}
    node_by_id = {node.id: node for node in graph.nodes}
    inbound = inbound_connections(graph)

    try:
        await run_registry.set_started(run_id)
        for node_id in topological_order(graph):
            node = node_by_id[node_id]
            await run_registry.set_node_started(run_id, node.id, node.type)
            node_inputs = _resolve_inputs(graph, node, inbound, outputs)
            handler = HANDLERS.get(node.type)
            if handler is None:
                raise BackendError(make_error("MISSING_NODE_HANDLER", f"No backend handler for node type {node.type}.", run_id=run_id, node_id=node.id, node_type=node.type))
            result = await handler(ctx, node, node_inputs)
            for key, payload in result.items():
                outputs[(node.id, key)] = payload
            await run_registry.set_node_completed(run_id, node.id, node.type)
        await run_registry.complete(run_id)
    except BackendError as exc:
        exc.error.run_id = exc.error.run_id or run_id
        await run_registry.add_error(run_id, exc.error)
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        await run_registry.add_error(
            run_id,
            make_error(
                "UNHANDLED_RUNTIME_ERROR",
                str(exc),
                run_id=run_id,
                details={"traceback": traceback.format_exc()},
            ),
        )


def _resolve_inputs(
    graph: WorkflowGraph,
    node: WorkflowNode,
    inbound: dict[tuple[str, str], object],
    outputs: dict[tuple[str, str], TypedPayload],
) -> dict[str, TypedPayload]:
    spec = spec_for(node.type)
    if spec is None:
        return {}
    result: dict[str, TypedPayload] = {}
    for input_key, port in spec.inputs.items():
        conn = inbound.get((node.id, input_key))
        if conn is None:
            continue
        payload = outputs.get((conn.from_.nodeId, conn.from_.key))
        if payload is None:
            raise BackendError(
                make_error(
                    "MISSING_UPSTREAM_OUTPUT",
                    "Upstream output was not produced.",
                    node_id=node.id,
                    node_type=node.type,
                    interface_key=input_key,
                    details={"source_node_id": conn.from_.nodeId, "source_key": conn.from_.key},
                )
            )
        if node.type in {"Merge", "SaveLigands"} and input_key == "ligand" and payload.type_name == "Batch Ligand":
            converted = payload
        else:
            converted = convert_payload(payload, port.type_name)
        if port.type_name == "Batch Structure":
            converted = converted.model_copy(update={"metadata": {**converted.metadata, "effective_type": payload.type_name}})
        result[input_key] = converted
    return result
