from __future__ import annotations

from backend.schemas.payloads import TypedPayload


def is_assignable(source: str, target: str) -> bool:
    if target == "Any" or source == "Any" or source == target:
        return True
    if target == "Batch Structure" and source in {"Batch Protein", "Batch Protein with Ligand", "Batch Structure"}:
        return True
    if target == "Protein" and source == "Batch Protein":
        return True
    if target == "Ligand" and source == "Batch Ligand":
        return True
    if target == "Ligand" and source == "Ligand":
        return True
    return False


def convert_payload(payload: TypedPayload, target_type: str) -> TypedPayload:
    if target_type == "Any" or payload.type_name == target_type:
        return payload
    if target_type == "Batch Structure" and payload.type_name in {"Batch Protein", "Batch Protein with Ligand"}:
        return payload.as_batch_structure()
    if target_type == "Protein" and payload.type_name == "Batch Protein":
        return payload.first("Protein")
    if target_type == "Ligand" and payload.type_name == "Batch Ligand":
        return payload.first("Ligand")
    return payload
