from __future__ import annotations

from backend.schemas.payloads import TypedPayload


def is_assignable(source: str, target: str) -> bool:
    if source == target:
        return True
    if target == "Batch Structure" and source in {"Batch Protein", "Batch Protein with Ligand", "Batch Protein (With Ligand)", "Batch Structure"}:
        return True
    if target == "Batch Protein" and source in {"Batch Protein with Ligand", "Batch Protein (With Ligand)", "Batch Structure"}:
        return True
    if target in {"Batch Protein with Ligand", "Batch Protein (With Ligand)"} and source in {"Batch Protein", "Batch Structure"}:
        return True
    if target == "Protein" and source == "Batch Protein":
        return True
    if target == "Ligand" and source == "Batch Ligand":
        return True
    if target == "Ligand" and source == "Ligand":
        return True
    return False


def convert_payload(payload: TypedPayload, target_type: str) -> TypedPayload:
    if payload.type_name == target_type:
        return payload
    if target_type == "Batch Structure" and payload.type_name in {"Batch Protein", "Batch Protein with Ligand", "Batch Protein (With Ligand)"}:
        return payload.as_batch_structure()
    if target_type == "Batch Protein" and payload.type_name in {"Batch Protein with Ligand", "Batch Protein (With Ligand)", "Batch Structure"}:
        return payload.model_copy(update={"type_name": "Batch Protein"})
    if target_type in {"Batch Protein with Ligand", "Batch Protein (With Ligand)"} and payload.type_name in {"Batch Protein", "Batch Structure"}:
        return payload.model_copy(update={"type_name": "Batch Protein (With Ligand)"})
    if target_type == "Protein" and payload.type_name == "Batch Protein":
        return payload.first("Protein")
    if target_type == "Ligand" and payload.type_name == "Batch Ligand":
        return payload.first("Ligand")
    return payload
