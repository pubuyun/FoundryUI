from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


PayloadType = Literal[
    "Ligand",
    "Protein",
    "List of Residues",
    "List of Atoms",
    "Batch Protein",
    "Batch Ligand",
    "Batch Protein with Ligand",
    "Batch Sequence",
    "Score",
    "Batch Structure",
    "Any",
]


class TypedPayload(BaseModel):
    type_name: str
    item_count: int = 0
    artifact_ids: list[str] = []
    paths: list[str] = []
    metadata: dict[str, Any] = {}
    data: Any = None

    def as_batch_structure(self) -> "TypedPayload":
        if self.type_name in {"Batch Protein", "Batch Protein with Ligand", "Batch Structure"}:
            return self.model_copy(update={"type_name": "Batch Structure"})
        return self

    def first(self, type_name: str) -> "TypedPayload":
        data = self.data[0] if isinstance(self.data, list) and self.data else self.data
        paths = self.paths[:1]
        artifact_ids = self.artifact_ids[:1]
        metadata = dict(self.metadata)
        residue_names = metadata.get("residue_names")
        if type_name == "Ligand" and isinstance(residue_names, list) and residue_names:
            metadata["residue_name"] = residue_names[0]
        return TypedPayload(
            type_name=type_name,
            item_count=1 if data is not None else 0,
            artifact_ids=artifact_ids,
            paths=paths,
            metadata=metadata,
            data=data,
        )
