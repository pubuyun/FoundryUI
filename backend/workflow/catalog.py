from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PortSpec:
    key: str
    type_name: str
    optional: bool = False
    label: str | None = None


@dataclass(frozen=True)
class OptionSpec:
    key: str
    kind: str
    default: Any = None
    required: bool = False
    choices: tuple[Any, ...] = ()
    min_value: float | None = None
    max_value: float | None = None
    label: str | None = None
    frontend_default: Any = None
    accept: str | None = None
    viewer_mode: str | None = None


@dataclass(frozen=True)
class NodeSpec:
    type_name: str
    inputs: dict[str, PortSpec] = field(default_factory=dict)
    options: dict[str, OptionSpec] = field(default_factory=dict)
    outputs: dict[str, PortSpec] = field(default_factory=dict)
    terminal: bool = False


def ports(items: list[PortSpec] | tuple[PortSpec, ...]) -> dict[str, PortSpec]:
    return {item.key: item for item in items}


def options(items: list[OptionSpec] | tuple[OptionSpec, ...]) -> dict[str, OptionSpec]:
    return {item.key: item for item in items}


def spec_for(node_type: str) -> NodeSpec | None:
    from backend.nodes.registry import node_for

    node = node_for(node_type)
    return node.spec if node is not None else None
