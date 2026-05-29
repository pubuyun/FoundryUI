from __future__ import annotations

import importlib
import pkgutil
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, ClassVar

from backend.nodes.common import ExecutionContext
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode
from backend.workflow.catalog import NodeSpec, OptionSpec, PortSpec, options, ports

NodeHandler = Callable[[ExecutionContext, WorkflowNode, dict[str, TypedPayload]], Awaitable[dict[str, TypedPayload]]]


class classproperty:
    def __init__(self, method):
        self.method = method

    def __get__(self, instance, owner):
        return self.method(owner)


@dataclass(frozen=True)
class UploadValidation:
    allowed_types: set[str]
    missing_message: str
    missing_code: str
    invalid_code: str


class FoundryNode:
    type_name: ClassVar[str] = ""
    title: ClassVar[str] = ""
    category: ClassVar[str] = "Other"
    description: ClassVar[str] = ""
    inputs: ClassVar[tuple[PortSpec, ...]] = ()
    options: ClassVar[tuple[OptionSpec, ...]] = ()
    outputs: ClassVar[tuple[PortSpec, ...]] = ()
    terminal: ClassVar[bool] = False
    aliases: ClassVar[tuple[str, ...]] = ()
    hidden: ClassVar[bool] = False
    ui: ClassVar[dict] = {}
    catalog_order: ClassVar[int] = 10000
    handler: ClassVar[NodeHandler | None] = None
    upload_validation: ClassVar[UploadValidation | None] = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.type_name:
            register_node(cls)

    @classproperty
    def spec(cls) -> NodeSpec:
        return NodeSpec(
            type_name=cls.type_name,
            inputs=ports(cls.inputs),
            options=options(cls.options),
            outputs=ports(cls.outputs),
            terminal=cls.terminal,
        )

    @classmethod
    async def execute(cls, ctx: ExecutionContext, workflow_node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
        if cls.handler is None:
            raise NotImplementedError(f"{cls.type_name} does not implement execute().")
        return await cls.handler(ctx, workflow_node, inputs)

    @staticmethod
    def ensure_score_alignment(ctx: ExecutionContext, node: WorkflowNode, structures: TypedPayload, scores: TypedPayload, input_keys: list[str]) -> None:
        expected = structures.item_count
        actual = scores.item_count
        if expected != actual:
            raise BackendError(
                make_error(
                    "SCORE_LENGTH_MISMATCH",
                    "Structure and score list lengths do not match.",
                    run_id=ctx.run_id,
                    node_id=node.id,
                    node_type=node.type,
                    details={"input_keys": input_keys, "expected_length": expected, "actual_length": actual},
                )
            )

    @classmethod
    def frontend_catalog_entry(cls, *, type_name: str | None = None, hidden: bool | None = None) -> dict:
        public_type = type_name or cls.type_name
        is_hidden = cls.hidden if hidden is None else hidden
        return {
            "type": public_type,
            "title": cls.title or _titleize(public_type),
            "category": cls.category,
            "description": cls.description,
            "inputs": [_port_to_frontend(port) for port in cls.inputs],
            "options": [_option_to_frontend(option) for option in cls.options],
            "outputs": [_port_to_frontend(port) for port in cls.outputs],
            "requiresRuntimeInput": bool(cls.ui.get("manual")),
            "hidden": is_hidden,
            "ui": dict(cls.ui),
        }


_NODES: dict[str, type[FoundryNode]] = {}
_DISCOVERED = False


def register_node(node_cls: type[FoundryNode]) -> type[FoundryNode]:
    if not node_cls.type_name:
        raise ValueError("Node classes must define type_name.")
    _register_name(node_cls.type_name, node_cls)
    for alias in node_cls.aliases:
        _register_name(alias, node_cls)
    return node_cls


def node_for(node_type: str) -> type[FoundryNode] | None:
    discover_nodes()
    return _NODES.get(node_type)


def registered_nodes(*, include_hidden: bool = True) -> list[type[FoundryNode]]:
    discover_nodes()
    seen: set[str] = set()
    nodes: list[type[FoundryNode]] = []
    for node_cls in _NODES.values():
        if node_cls.type_name in seen:
            continue
        seen.add(node_cls.type_name)
        if include_hidden or not node_cls.hidden:
            nodes.append(node_cls)
    return sorted(nodes, key=lambda item: (item.catalog_order, item.type_name))


def discover_nodes() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    _DISCOVERED = True
    base_dir = Path(__file__).parent
    for package in (
        "note",
        "selector",
        "filter",
        "input",
        "generation",
        "mpnn",
        "folding",
        "scoring",
        "logic",
        "utility",
        "viewer",
        "save",
    ):
        package_dir = base_dir / package
        if not package_dir.is_dir():
            continue
        for module in pkgutil.iter_modules([str(package_dir)]):
            if module.name.startswith("_") or module.name == "base":
                continue
            importlib.import_module(f"{__package__}.{package}.{module.name}")
    validate_registry()


def validate_registry() -> None:
    for name, node_cls in _NODES.items():
        if node_cls.spec is None:
            raise ValueError(f"Node {name} has no spec.")
        _validate_unique_keys(name, "input", [port.key for port in node_cls.inputs])
        _validate_unique_keys(name, "option", [option.key for option in node_cls.options])
        _validate_unique_keys(name, "output", [port.key for port in node_cls.outputs])
        if node_cls.handler is None and getattr(node_cls.execute, "__func__", None) is getattr(FoundryNode.execute, "__func__", None):
            raise ValueError(f"Node {name} has no handler or execute method.")


def _register_name(name: str, node_cls: type[FoundryNode]) -> None:
    existing = _NODES.get(name)
    if existing is not None and existing is not node_cls:
        raise ValueError(f"Duplicate node registration for {name}: {existing.__name__} and {node_cls.__name__}")
    _NODES[name] = node_cls


def _validate_unique_keys(node_type: str, label: str, keys: list[str]) -> None:
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            raise ValueError(f"Node {node_type} has duplicate {label} key {key!r}.")
        seen.add(key)


def _port_to_frontend(port: PortSpec) -> dict:
    return {
        "key": port.key,
        "label": port.label or _labelize(port.key, port.type_name),
        "type": port.type_name,
        "optional": port.optional,
    }


def _option_to_frontend(option: OptionSpec) -> dict:
    value = option.frontend_default if option.frontend_default is not None else option.default
    result = {
        "key": option.key,
        "label": option.label or _labelize(option.key),
        "kind": option.kind,
        "value": "" if value is None else value,
    }
    if option.choices:
        result["items"] = list(option.choices)
    if option.min_value is not None:
        result["min"] = option.min_value
    if option.max_value is not None:
        result["max"] = option.max_value
    if option.accept:
        result["accept"] = option.accept
    if option.viewer_mode:
        result["viewerMode"] = option.viewer_mode
    elif option.kind == "viewer":
        result["viewerMode"] = "structure"
    return result


def _titleize(value: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r" \1", value).replace(" 3", "3")


def _labelize(key: str, type_name: str | None = None) -> str:
    if type_name and key.lower() in {"protein", "ligand", "score", "structures", "complexes", "sequences"}:
        return type_name
    return re.sub(r"(?<!^)([A-Z])", r" \1", key).replace("_", " ").strip().title()
