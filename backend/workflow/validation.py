from __future__ import annotations

from backend.schemas.errors import StructuredError, make_error
from backend.schemas.workflow import WorkflowGraph
from backend.workflow.catalog import spec_for
from backend.workflow.graph import has_cycle, inbound_connections
from backend.workflow.type_conversions import is_assignable


def _is_batch_type(type_name: str | None) -> bool:
    return bool(type_name and type_name.startswith("Batch "))


def _option_value(node_options: dict, key: str, default):
    return node_options[key] if key in node_options else default


def validate_workflow(graph: WorkflowGraph) -> list[StructuredError]:
    errors: list[StructuredError] = []
    node_ids = {node.id for node in graph.nodes}

    if has_cycle(graph):
        errors.append(make_error("WORKFLOW_CYCLE", "Workflow graph contains a cycle."))

    for node in graph.nodes:
        spec = spec_for(node.type)
        if spec is None:
            errors.append(make_error("UNKNOWN_NODE_TYPE", f"Unknown node type: {node.type}", node_id=node.id, node_type=node.type))
            continue

        for input_key in node.inputs:
            if input_key not in spec.inputs:
                errors.append(
                    make_error(
                        "UNKNOWN_INPUT_PORT",
                        f"Unknown input port {input_key!r} for node type {node.type}.",
                        node_id=node.id,
                        node_type=node.type,
                        interface_key=input_key,
                    )
                )
        for output_key in node.outputs:
            if output_key not in spec.outputs:
                errors.append(
                    make_error(
                        "UNKNOWN_OUTPUT_PORT",
                        f"Unknown output port {output_key!r} for node type {node.type}.",
                        node_id=node.id,
                        node_type=node.type,
                        interface_key=output_key,
                    )
                )

        for key, option in spec.options.items():
            value = _option_value(node.options, key, option.default)
            if option.required and (value is None or value == ""):
                errors.append(
                    make_error(
                        "MISSING_REQUIRED_OPTION",
                        f"Required option {key!r} is missing.",
                        node_id=node.id,
                        node_type=node.type,
                        option_key=key,
                    )
                )
                continue
            if value is None or value == "":
                continue
            if option.choices and value not in option.choices:
                errors.append(
                    make_error(
                        "INVALID_OPTION_VALUE",
                        f"Invalid value for option {key!r}.",
                        node_id=node.id,
                        node_type=node.type,
                        option_key=key,
                        details={"value": value, "allowed": list(option.choices)},
                    )
                )
            if option.kind in {"int", "float"}:
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    errors.append(
                        make_error(
                            "INVALID_OPTION_TYPE",
                            f"Option {key!r} must be numeric.",
                            node_id=node.id,
                            node_type=node.type,
                            option_key=key,
                            details={"value": value},
                        )
                    )
                    continue
                if option.min_value is not None and numeric < option.min_value:
                    errors.append(
                        make_error(
                            "INVALID_OPTION_VALUE",
                            f"Option {key!r} is below the minimum.",
                            node_id=node.id,
                            node_type=node.type,
                            option_key=key,
                            details={"value": value, "min": option.min_value},
                        )
                    )
                if option.max_value is not None and numeric > option.max_value:
                    errors.append(
                        make_error(
                            "INVALID_OPTION_VALUE",
                            f"Option {key!r} is above the maximum.",
                            node_id=node.id,
                            node_type=node.type,
                            option_key=key,
                            details={"value": value, "max": option.max_value},
                        )
                    )

    inbound = inbound_connections(graph)
    inbound_counts: dict[tuple[str, str], int] = {}
    node_by_id = {node.id: node for node in graph.nodes}
    for conn in graph.connections:
        inbound_counts[(conn.to.nodeId, conn.to.key)] = inbound_counts.get((conn.to.nodeId, conn.to.key), 0) + 1
        if conn.from_.nodeId not in node_ids:
            errors.append(make_error("UNKNOWN_SOURCE_NODE", "Connection references an unknown source node.", details=conn.model_dump(by_alias=True)))
            continue
        if conn.to.nodeId not in node_ids:
            errors.append(make_error("UNKNOWN_TARGET_NODE", "Connection references an unknown target node.", details=conn.model_dump(by_alias=True)))
            continue

        source_node = node_by_id[conn.from_.nodeId]
        target_node = node_by_id[conn.to.nodeId]
        source_spec = spec_for(source_node.type)
        target_spec = spec_for(target_node.type)
        if source_spec is None or target_spec is None:
            continue
        source_port = source_spec.outputs.get(conn.from_.key)
        target_port = target_spec.inputs.get(conn.to.key)
        if source_port is None:
            errors.append(
                make_error(
                    "UNKNOWN_OUTPUT_PORT",
                    f"Unknown output port {conn.from_.key!r}.",
                    node_id=source_node.id,
                    node_type=source_node.type,
                    interface_key=conn.from_.key,
                )
            )
            continue
        if target_port is None:
            errors.append(
                make_error(
                    "UNKNOWN_INPUT_PORT",
                    f"Unknown input port {conn.to.key!r}.",
                    node_id=target_node.id,
                    node_type=target_node.type,
                    interface_key=conn.to.key,
                )
            )
            continue
        if not is_assignable(source_port.type_name, target_port.type_name):
            errors.append(
                make_error(
                    "INVALID_TYPE_CONVERSION",
                    f"Cannot connect {source_port.type_name} to {target_port.type_name}.",
                    node_id=target_node.id,
                    node_type=target_node.type,
                    interface_key=conn.to.key,
                    details={"source_type": source_port.type_name, "target_type": target_port.type_name},
                )
            )

    for node in graph.nodes:
        spec = spec_for(node.type)
        if spec is None:
            continue
        for key, count in inbound_counts.items():
            node_id, input_key = key
            if node_id != node.id or count <= 1:
                continue
            port = spec.inputs.get(input_key)
            if port is not None and not _is_batch_type(port.type_name):
                errors.append(
                    make_error(
                        "MULTIPLE_CONNECTIONS_TO_NON_BATCH_INPUT",
                        f"Input port {input_key!r} can only receive one connection.",
                        node_id=node.id,
                        node_type=node.type,
                        interface_key=input_key,
                        details={"connection_count": count, "target_type": port.type_name},
                    )
                )

    for node in graph.nodes:
        spec = spec_for(node.type)
        if spec is None:
            continue
        for key, port in spec.inputs.items():
            if not port.optional and (node.id, key) not in inbound:
                errors.append(
                    make_error(
                        "DISCONNECTED_REQUIRED_PORT",
                        f"Required input port {key!r} is not connected.",
                        node_id=node.id,
                        node_type=node.type,
                        interface_key=key,
                    )
                )

    return errors
