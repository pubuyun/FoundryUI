from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PortDeclaration(BaseModel):
    label: str | None = None
    type: str | None = None
    optional: bool = False


class WorkflowNode(BaseModel):
    id: str
    type: str
    title: str | None = None
    position: dict[str, Any] | None = None
    inputs: dict[str, PortDeclaration] = {}
    options: dict[str, Any] = {}
    outputs: dict[str, PortDeclaration] = {}


class ConnectionEndpoint(BaseModel):
    nodeId: str
    key: str
    type: str | None = None


class WorkflowConnection(BaseModel):
    from_: ConnectionEndpoint = Field(alias="from")
    to: ConnectionEndpoint

    model_config = {"populate_by_name": True}


class WorkflowGraph(BaseModel):
    nodes: list[WorkflowNode] = []
    connections: list[WorkflowConnection] = []


class EmbeddedUpload(BaseModel):
    name: str
    type: str | None = None
    content: str


class FoundryWorkflowDocument(BaseModel):
    fileType: str | None = None
    extension: str | None = None
    version: int | str | None = None
    savedAt: str | None = None
    baklava: dict[str, Any] | None = None
    workflow: WorkflowGraph
    uploads: dict[str, list[EmbeddedUpload]] = {}


class RunCreateRequest(BaseModel):
    workflow: WorkflowGraph | None = None
    document: FoundryWorkflowDocument | None = None
    uploads: dict[str, list[EmbeddedUpload]] = {}
    run_name: str | None = None

    def workflow_graph(self) -> WorkflowGraph:
        if self.document is not None:
            return self.document.workflow
        if self.workflow is None:
            raise ValueError("workflow or document is required")
        return self.workflow

    def embedded_uploads(self) -> dict[str, list[EmbeddedUpload]]:
        merged = dict(self.uploads)
        if self.document is not None:
            merged.update(self.document.uploads)
        return merged


class WorkflowValidationResponse(BaseModel):
    valid: bool
    errors: list[Any] = []
    warnings: list[Any] = []
    node_count: int = 0
    connection_count: int = 0
