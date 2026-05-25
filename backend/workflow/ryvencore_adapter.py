from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path

import ryvencore as rc

from backend.artifacts.registry import artifact_store
from backend.nodes.common import ExecutionContext
from backend.nodes.dispatch import HANDLERS
from backend.runtime.registry import run_registry
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import RunCreateRequest, WorkflowNode
from backend.workflow.catalog import NodeSpec, spec_for
from backend.workflow.graph import inbound_connections
from backend.workflow.type_conversions import convert_payload


class FoundryPayloadData(rc.Data):
    identifier = "FoundryPayloadData"

    @property
    def payload(self) -> TypedPayload:
        return self._payload.model_copy(deep=True)

    @payload.setter
    def payload(self, value: TypedPayload) -> None:
        self._payload = value

    def get_data(self):
        return self.payload.model_dump()

    def set_data(self, data):
        self.payload = TypedPayload.model_validate(data)


class FoundryRyvencoreNode(rc.Node):
    title = "Foundry Node"
    init_inputs: list[rc.NodeInputType] = []
    init_outputs: list[rc.NodeOutputType] = []
    workflow_node: WorkflowNode
    node_spec: NodeSpec
    input_keys: list[str]
    logical_input_keys: list[str]
    output_keys: list[str]
    exec_context: ExecutionContext
    runtime_loop: asyncio.AbstractEventLoop
    connected_input_keys: set[str]
    _foundry_executed: bool = False

    def update_event(self, inp=-1):
        if self._foundry_executed:
            return
        if not self._inputs_ready():
            return
        self._foundry_executed = True
        input_payloads = self._input_payloads()

        async def execute() -> tuple[dict[str, TypedPayload], str]:
            if self.exec_context.registry.is_cancel_requested(self.exec_context.run_id):
                raise BackendError(
                    make_error(
                        "RUN_CANCELLED",
                        "Run was stopped by the user.",
                        run_id=self.exec_context.run_id,
                        node_id=self.workflow_node.id,
                        node_type=self.workflow_node.type,
                        recoverable=True,
                    )
                )
            cache_key = _node_cache_key(self.workflow_node, input_payloads, self.exec_context.uploads)
            await self.exec_context.registry.set_node_started(
                self.exec_context.run_id,
                self.workflow_node.id,
                self.workflow_node.type,
            )
            try:
                cached = None
                if self.workflow_node.type not in {"AtomSelector", "ResidueSelector", "FilterAtomsChirality"}:
                    cached = await _reuse_cached_outputs(self.exec_context, self.workflow_node, self.output_keys, cache_key)
                if cached is not None:
                    await self.exec_context.registry.set_node_completed(
                        self.exec_context.run_id,
                        self.workflow_node.id,
                        self.workflow_node.type,
                        cached=True,
                    )
                    return cached, cache_key
                handler = HANDLERS.get(self.workflow_node.type)
                if handler is None:
                    raise BackendError(
                        make_error(
                            "MISSING_NODE_HANDLER",
                            f"No backend handler for node type {self.workflow_node.type}.",
                            run_id=self.exec_context.run_id,
                            node_id=self.workflow_node.id,
                            node_type=self.workflow_node.type,
                        )
                    )
                result = await handler(self.exec_context, self.workflow_node, input_payloads)
                await self.exec_context.registry.set_node_completed(
                    self.exec_context.run_id,
                    self.workflow_node.id,
                    self.workflow_node.type,
                )
                return result, cache_key
            except Exception:
                raise

        result, cache_key = self.runtime_loop.run_until_complete(execute())
        self.runtime_loop.run_until_complete(self.exec_context.registry.record_node_cache_key(self.exec_context.run_id, self.workflow_node.id, cache_key))
        for key, payload in result.items():
            if key in self.output_keys:
                self.runtime_loop.run_until_complete(self.exec_context.registry.record_output(self.exec_context.run_id, self.workflow_node.id, key, payload))
                self.set_output_val(self.output_keys.index(key), FoundryPayloadData(payload))

    def _inputs_ready(self) -> bool:
        for index, key in enumerate(self.logical_input_keys):
            port = self.node_spec.inputs[key]
            data = self.input(index)
            if data is None and (not port.optional or key in self.connected_input_keys):
                return False
        return True

    def _input_payloads(self) -> dict[str, TypedPayload]:
        payloads: dict[str, TypedPayload] = {}
        grouped: dict[str, list[TypedPayload]] = {}
        for index, key in enumerate(self.logical_input_keys):
            data = self.input(index)
            if data is None:
                continue
            port = self.node_spec.inputs[key]
            source_payload = data.payload
            payload = convert_payload(source_payload, port.type_name)
            if port.type_name == "Batch Structure":
                payload = payload.model_copy(
                    update={"metadata": {**payload.metadata, "effective_type": source_payload.type_name}}
                )
            if self.workflow_node.type in {"Merge", "SaveLigands"} and key == "ligand" and source_payload.type_name == "Batch Ligand":
                payload = source_payload
            grouped.setdefault(key, []).append(payload)
        for key, values in grouped.items():
            payloads[key] = _combine_payloads(values) if len(values) > 1 else values[0]
        return payloads


def execute_ryvencore_workflow(
    *,
    run_id: str,
    request: RunCreateRequest,
) -> None:
    graph = request.workflow_graph()
    ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads=request.embedded_uploads())
    runtime_loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(runtime_loop)
        session = rc.Session(load_addons=True)
        session.register_data_type(FoundryPayloadData)
        flow = session.create_flow(f"FoundryUI {run_id}")
        flow.set_algorithm_mode("data")

        node_classes: dict[str, type[FoundryRyvencoreNode]] = {}
        flow_nodes: dict[str, FoundryRyvencoreNode] = {}
        update_errors: list[Exception] = []
        connected_inputs = inbound_connections(graph)
        incoming_counts: dict[tuple[str, str], int] = {}
        for connection in graph.connections:
            key = (connection.to.nodeId, connection.to.key)
            incoming_counts[key] = incoming_counts.get(key, 0) + 1
        for workflow_node in graph.nodes:
            node_spec = spec_for(workflow_node.type)
            if node_spec is None:
                raise BackendError(
                    make_error(
                        "UNKNOWN_NODE_TYPE",
                        f"Unknown node type: {workflow_node.type}",
                        run_id=run_id,
                        node_id=workflow_node.id,
                        node_type=workflow_node.type,
                    )
                )
            connected_input_keys = {key for node_id, key in connected_inputs if node_id == workflow_node.id}
            node_class = _node_class_for(workflow_node, node_spec, ctx, runtime_loop, connected_input_keys, incoming_counts)
            node_classes[workflow_node.id] = node_class
            session.register_node_type(node_class)
            flow_node = flow.create_node(node_class)
            if flow_node is None:
                raise BackendError(
                    make_error(
                        "RYVENCORE_NODE_CREATE_FAILED",
                        f"Ryvencore could not create node {workflow_node.id}.",
                        run_id=run_id,
                        node_id=workflow_node.id,
                        node_type=workflow_node.type,
                    )
                )
            flow_nodes[workflow_node.id] = flow_node
            flow_node.update_error.sub(update_errors.append)

        used_input_slots: dict[tuple[str, str], int] = {}
        for connection in graph.connections:
            source = flow_nodes[connection.from_.nodeId]
            target = flow_nodes[connection.to.nodeId]
            source_class = node_classes[connection.from_.nodeId]
            target_class = node_classes[connection.to.nodeId]
            source_index = source_class.output_keys.index(connection.from_.key)
            target_slots = target_class.input_slot_indices[connection.to.key]
            used_key = (connection.to.nodeId, connection.to.key)
            used_index = used_input_slots.get(used_key, 0)
            target_index = target_slots[min(used_index, len(target_slots) - 1)]
            used_input_slots[used_key] = used_index + 1
            created = flow.connect_nodes(source.outputs[source_index], target.inputs[target_index])
            if created is None:
                raise BackendError(
                    make_error(
                        "RYVENCORE_CONNECTION_FAILED",
                        "Ryvencore rejected a workflow connection.",
                        run_id=run_id,
                        node_id=connection.to.nodeId,
                        interface_key=connection.to.key,
                        details=connection.model_dump(by_alias=True),
                    )
                )

        for workflow_node in graph.nodes:
            if update_errors:
                break
            node_spec = spec_for(workflow_node.type)
            if node_spec is None:
                continue
            if all((workflow_node.id, key) not in connected_inputs for key in node_spec.inputs):
                flow_nodes[workflow_node.id].update()

        if update_errors:
            first = update_errors[0]
            if isinstance(first, BackendError):
                raise first
            raise BackendError(
                make_error(
                    "RYVENCORE_NODE_ERROR",
                    str(first),
                    run_id=run_id,
                )
            )
    finally:
        runtime_loop.close()
        asyncio.set_event_loop(None)


def _node_class_for(
    workflow_node: WorkflowNode,
    node_spec: NodeSpec,
    ctx: ExecutionContext,
    runtime_loop: asyncio.AbstractEventLoop,
    connected_input_keys: set[str],
    incoming_counts: dict[tuple[str, str], int],
) -> type[FoundryRyvencoreNode]:
    logical_input_keys: list[str] = []
    input_socket_keys: list[str] = []
    input_slot_indices: dict[str, list[int]] = {}
    for key, port in node_spec.inputs.items():
        count = incoming_counts.get((workflow_node.id, key), 0)
        socket_count = max(1, count) if port.type_name.startswith("Batch ") else 1
        input_slot_indices[key] = []
        for index in range(socket_count):
            socket_key = key if index == 0 else f"{key}__{index + 1}"
            input_slot_indices[key].append(len(input_socket_keys))
            input_socket_keys.append(socket_key)
            logical_input_keys.append(key)
    output_keys = list(node_spec.outputs.keys())
    safe_id = re.sub(r"\W+", "_", workflow_node.id)
    return type(
        f"FoundryNode_{safe_id}",
        (FoundryRyvencoreNode,),
        {
            "identifier": f"FoundryUI.{workflow_node.id}",
            "title": workflow_node.title or workflow_node.type,
            "workflow_node": workflow_node,
            "node_spec": node_spec,
            "input_keys": input_socket_keys,
            "logical_input_keys": logical_input_keys,
            "input_slot_indices": input_slot_indices,
            "output_keys": output_keys,
            "exec_context": ctx,
            "runtime_loop": runtime_loop,
            "connected_input_keys": connected_input_keys,
            "init_inputs": [rc.NodeInputType(key) for key in input_socket_keys],
            "init_outputs": [rc.NodeOutputType(key) for key in output_keys],
        },
    )


def _combine_payloads(values: list[TypedPayload]) -> TypedPayload:
    first = values[0]
    data = []
    paths: list[str] = []
    artifact_ids: list[str] = []
    for payload in values:
        if isinstance(payload.data, list):
            data.extend(payload.data)
        elif payload.data is not None:
            data.append(payload.data)
        paths.extend(payload.paths)
        artifact_ids.extend(payload.artifact_ids)
    metadata = dict(first.metadata)
    metadata["combined_from_types"] = [payload.type_name for payload in values]
    return first.model_copy(
        update={
            "item_count": len(data) if data else sum(payload.item_count for payload in values),
            "artifact_ids": artifact_ids,
            "paths": paths,
            "data": data,
            "metadata": metadata,
        }
    )


def _node_cache_key(node: WorkflowNode, input_payloads: dict[str, TypedPayload], uploads: dict[str, list]) -> str:
    upload_fingerprints = []
    for item in uploads.get(node.id, []):
        content = getattr(item, "content", "")
        upload_fingerprints.append(
            {
                "name": getattr(item, "name", ""),
                "type": getattr(item, "type", None),
                "sha256": hashlib.sha256(str(content).encode()).hexdigest(),
            }
        )
    inputs = {
        key: {
            "type_name": payload.type_name,
            "item_count": payload.item_count,
            "metadata": payload.metadata,
            "data_sha256": hashlib.sha256(json.dumps(payload.data, sort_keys=True, default=str).encode()).hexdigest(),
        }
        for key, payload in sorted(input_payloads.items())
    }
    data = {
        "node_type": node.type,
        "options": node.options,
        "uploads": upload_fingerprints,
        "inputs": inputs,
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


async def _reuse_cached_outputs(ctx: ExecutionContext, node: WorkflowNode, output_keys: list[str], cache_key: str) -> dict[str, TypedPayload] | None:
    previous_run_id = getattr(ctx.registry.get(ctx.run_id).request, "previous_run_id", None)
    if not previous_run_id:
        return None
    previous = ctx.registry.get(previous_run_id)
    if previous is None or previous.node_cache_keys.get(node.id) != cache_key:
        return None

    reused: dict[str, TypedPayload] = {}
    for output_key in output_keys:
        previous_payload = previous.outputs.get((node.id, output_key))
        if previous_payload is None:
            continue
        typed = TypedPayload.model_validate(previous_payload)
        artifacts = []
        for index, rel_path in enumerate(typed.paths, start=1):
            source = ctx.store.absolute(previous_run_id, rel_path)
            if not source.is_file():
                return None
            destination = _cached_destination(ctx, node, output_key, index, source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            artifact = ctx.store.register_file(
                run_id=ctx.run_id,
                path=destination,
                payload_type=typed.type_name,
                node_id=node.id,
                node_type=node.type,
            )
            await ctx.artifact_created(artifact)
            artifacts.append(artifact)
        reused[output_key] = typed.model_copy(
            update={
                "artifact_ids": [artifact.artifact_id for artifact in artifacts],
                "paths": [artifact.path for artifact in artifacts],
            }
        )
    return reused if reused else None


def _cached_destination(ctx: ExecutionContext, node: WorkflowNode, output_key: str, index: int, source: Path) -> Path:
    suffix = "".join(source.suffixes) or ".dat"
    stem = source.name[: -len(suffix)] if suffix and source.name.endswith(suffix) else source.stem
    safe_stem = re.sub(r"\W+", "_", stem).strip("_") or output_key
    base = artifact_store.node_dir(ctx.run_id, node.id, node.type) / f"{safe_stem}_cached_{index:04d}{suffix}"
    if not base.exists():
        return base
    for attempt in range(2, 1000):
        candidate = base.with_name(f"{safe_stem}_cached_{index:04d}_{attempt}{suffix}")
        if not candidate.exists():
            return candidate
    return base.with_name(f"{safe_stem}_cached_{index:04d}_{uuid.uuid4().hex}{suffix}")
