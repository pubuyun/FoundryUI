from __future__ import annotations

from backend.schemas.payloads import TypedPayload


def canonical_type(type_name: str) -> str:
    if type_name == "Protein Atoms List":
        return "Residues Atoms List"
    return type_name


def is_assignable(source: str, target: str) -> bool:
    source = canonical_type(source)
    target = canonical_type(target)
    if source == target:
        return True
    if target == "Batch Structure" and source in {"Batch Protein", "Batch Protein with Ligand", "Batch Protein (With Ligand)", "Batch Structure"}:
        return True
    if target == "Batch Protein" and source in {"Batch Protein with Ligand", "Batch Protein (With Ligand)", "Batch Structure"}:
        return True
    if target == "Batch Protein with Ligand" and source == "Batch Protein (With Ligand)":
        return True
    if target == "Batch Protein (With Ligand)" and source in {"Batch Protein", "Batch Protein with Ligand", "Batch Structure"}:
        return True
    if target == "Protein" and source in {"Batch Protein", "Batch Protein with Ligand", "Batch Protein (With Ligand)"}:
        return True
    if target == "Ligand" and source == "Batch Ligand":
        return True
    if target == "Ligand" and source == "Ligand":
        return True
    if target == "Batch Ligand" and source == "Ligand":
        return True
    if target == "Batch Protein (With Ligand)" and source in {"Ligand", "Batch Ligand", "Protein"}:
        return True
    return False


def convert_payload(payload: TypedPayload, target_type: str) -> TypedPayload:
    target_type = canonical_type(target_type)
    if payload.type_name == "Protein Atoms List":
        payload = payload.model_copy(update={"type_name": "Residues Atoms List"})
    if payload.type_name == target_type:
        return payload
    if target_type == "Batch Structure" and payload.type_name in {"Batch Protein", "Batch Protein with Ligand", "Batch Protein (With Ligand)"}:
        return payload.as_batch_structure()
    if target_type == "Batch Protein" and payload.type_name in {"Batch Protein with Ligand", "Batch Protein (With Ligand)", "Batch Structure"}:
        return payload.model_copy(update={"type_name": "Batch Protein"})
    if target_type == "Batch Protein with Ligand" and payload.type_name == "Batch Protein (With Ligand)":
        return payload.model_copy(update={"type_name": "Batch Protein with Ligand"})
    if target_type == "Batch Protein (With Ligand)" and payload.type_name in {"Batch Protein", "Batch Protein with Ligand", "Batch Structure"}:
        return payload.model_copy(update={"type_name": "Batch Protein (With Ligand)"})
    if target_type == "Protein" and payload.type_name in {"Batch Protein", "Batch Protein with Ligand", "Batch Protein (With Ligand)"}:
        return payload.first("Protein")
    if target_type == "Ligand" and payload.type_name == "Batch Ligand":
        return payload.first("Ligand")
    return payload
