from __future__ import annotations

import asyncio
import re

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
    output_keys: list[str]
    exec_context: ExecutionContext
    runtime_loop: asyncio.AbstractEventLoop
    connected_input_keys: set[str]

    def update_event(self, inp=-1):
        if not self._inputs_ready():
            return

        async def execute() -> dict[str, TypedPayload]:
            await self.exec_context.registry.set_node_started(
                self.exec_context.run_id,
                self.workflow_node.id,
                self.workflow_node.type,
            )
            try:
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
                result = await handler(self.exec_context, self.workflow_node, self._input_payloads())
                await self.exec_context.registry.set_node_completed(
                    self.exec_context.run_id,
                    self.workflow_node.id,
                    self.workflow_node.type,
                )
                return result
            except Exception:
                raise

        result = self.runtime_loop.run_until_complete(execute())
        for key, payload in result.items():
            if key in self.output_keys:
                self.set_output_val(self.output_keys.index(key), FoundryPayloadData(payload))

    def _inputs_ready(self) -> bool:
        for index, key in enumerate(self.input_keys):
            port = self.node_spec.inputs[key]
            data = self.input(index)
            if data is None and (not port.optional or key in self.connected_input_keys):
                return False
        return True

    def _input_payloads(self) -> dict[str, TypedPayload]:
        payloads: dict[str, TypedPayload] = {}
        for index, key in enumerate(self.input_keys):
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
            payloads[key] = payload
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
            node_class = _node_class_for(workflow_node, node_spec, ctx, runtime_loop, connected_input_keys)
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

        for connection in graph.connections:
            source = flow_nodes[connection.from_.nodeId]
            target = flow_nodes[connection.to.nodeId]
            source_class = node_classes[connection.from_.nodeId]
            target_class = node_classes[connection.to.nodeId]
            source_index = source_class.output_keys.index(connection.from_.key)
            target_index = target_class.input_keys.index(connection.to.key)
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
) -> type[FoundryRyvencoreNode]:
    input_keys = list(node_spec.inputs.keys())
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
            "input_keys": input_keys,
            "output_keys": output_keys,
            "exec_context": ctx,
            "runtime_loop": runtime_loop,
            "connected_input_keys": connected_input_keys,
            "init_inputs": [rc.NodeInputType(key) for key in input_keys],
            "init_outputs": [rc.NodeOutputType(key) for key in output_keys],
        },
    )
