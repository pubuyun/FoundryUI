from __future__ import annotations

import asyncio
import json

from backend.bio.pdb import filter_pdb_chains, filter_pdb_residues, list_atom_names, list_chain_ids, list_residue_ids, residue_atom_map
from backend.nodes.common import ExecutionContext, node_dir, option, payload_from_artifacts, read_payload_files, split_selector
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def atom_selector(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    values = await _runtime_selector_values(ctx, node, inputs, "atoms") if inputs else {}
    atoms = split_selector(values.get("atoms", option(node, "atoms", "")))
    if inputs and atoms:
        _validate_atoms_exist(ctx, node, inputs, atoms, "atoms")
    artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "atoms.json", atoms, "List of Atoms", item_count=len(atoms))
    return {"atoms": payload_from_artifacts("List of Atoms", [artifact], data=atoms)}


async def residue_selector(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    values = await _runtime_selector_values(ctx, node, inputs, "residues") if inputs else {}
    residues = split_selector(values.get("residues", option(node, "residues", "")))
    if inputs and residues:
        _validate_residues_exist(ctx, node, inputs, residues, "residues")
    artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "residues.json", residues, "List of Residues", item_count=len(residues))
    return {"residues": payload_from_artifacts("List of Residues", [artifact], data=residues)}


async def protein_chain_selector(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    values = await _runtime_selector_values(ctx, node, inputs, "chains")
    chains = split_selector(values.get("chains", option(node, "chains", "")))
    if not chains:
        raise BackendError(make_error("MISSING_CHAIN_SELECTION", "ProteinChainSelector requires at least one selected chain.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="chains"))
    proteins = read_payload_files(ctx, inputs["batchProtein"])
    _validate_chains_exist(ctx, node, proteins, chains)
    out_dir = node_dir(ctx, node)
    artifacts = []
    filtered = []
    for index, protein in enumerate(proteins, start=1):
        content = filter_pdb_chains(protein, chains)
        artifact = await ctx.write_text_artifact(node, out_dir / f"protein_{index:04d}.pdb", content, "Batch Protein", "chemical/x-pdb")
        artifacts.append(artifact)
        filtered.append(content)
    return {"batchProtein": payload_from_artifacts("Batch Protein", artifacts, data=filtered)}


async def protein_atom_selector(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    residues = _residue_values(inputs.get("residues"))
    protein = inputs.get("protein")
    if protein is None:
        raise BackendError(
            make_error(
                "MISSING_PROTEIN_INPUT",
                "ProteinAtomSelector requires a protein input.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                interface_key="protein",
            )
        )

    request_inputs: dict[str, TypedPayload] = {}
    protein_files = read_payload_files(ctx, protein)
    if protein_files and residues:
        _validate_residues_in_contents(ctx, node, protein_files, residues, "residues")
        selected_pdb = filter_pdb_residues(protein_files[0], residues)
        preview = await ctx.write_text_artifact(
            node,
            node_dir(ctx, node) / "selected_residues_for_atom_selection.pdb",
            selected_pdb,
            "Protein",
            media_type="chemical/x-pdb",
        )
        request_inputs["selectedResidues"] = payload_from_artifacts("Protein", [preview], data=selected_pdb)
    else:
        request_inputs["protein"] = protein

    values = await _runtime_selector_values(ctx, node, request_inputs, "proteinAtoms")
    atoms = _parse_protein_atom_map(ctx, node, values.get("proteinAtoms", option(node, "proteinAtoms", "")))
    if atoms:
        _validate_protein_atoms_exist(ctx, node, protein_files, atoms)
    artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "residue_atoms.json", atoms, "Residues Atoms List", item_count=len(atoms))
    return {"proteinAtoms": payload_from_artifacts("Residues Atoms List", [artifact], data=atoms, item_count=len(atoms))}


async def _runtime_selector_values(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload], field: str) -> dict:
    payloads = {
        key: {
            "type_name": payload.type_name,
            "item_count": payload.item_count,
            "artifact_ids": payload.artifact_ids,
            "paths": payload.paths,
            "metadata": payload.metadata,
        }
        for key, payload in inputs.items()
    }
    try:
        return await ctx.registry.request_node_input(
            ctx.run_id,
            node.id,
            node.type,
            [field],
            payloads,
            {field: option(node, field, "")},
        )
    except asyncio.CancelledError as exc:
        raise BackendError(
            make_error(
                "RUN_CANCELLED",
                "Run was stopped while waiting for selector input.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                recoverable=True,
            )
        ) from exc


def _residue_values(payload: TypedPayload | None) -> list[str]:
    if payload is None:
        return []
    if isinstance(payload.data, list):
        return [str(item).strip() for item in payload.data if str(item).strip()]
    if isinstance(payload.data, str):
        return split_selector(payload.data)
    return []


def _parse_protein_atom_map(ctx: ExecutionContext, node: WorkflowNode, value) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(residue).strip(): _atom_list_text(atoms) for residue, atoms in value.items() if str(residue).strip() and _atom_list_text(atoms)}
    text = str(value or "").strip()
    if not text:
        return {}
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise BackendError(
                make_error(
                    "INVALID_PROTEIN_ATOM_SELECTION",
                    "ProteinAtomSelector atom selection JSON is not valid.",
                    run_id=ctx.run_id,
                    node_id=node.id,
                    node_type=node.type,
                    option_key="proteinAtoms",
                    details={"selection": text},
                )
            ) from exc
        if not isinstance(data, dict):
            raise BackendError(
                make_error(
                    "INVALID_PROTEIN_ATOM_SELECTION",
                    "ProteinAtomSelector atom selection JSON must be an object mapping residues to atom names.",
                    run_id=ctx.run_id,
                    node_id=node.id,
                    node_type=node.type,
                    option_key="proteinAtoms",
                    details={"selection": text},
                )
            )
        return _parse_protein_atom_map(ctx, node, data)
    result: dict[str, str] = {}
    invalid_entries: list[str] = []
    for entry in [part.strip() for part in text.replace("\n", ";").split(";") if part.strip()]:
        if ":" not in entry:
            invalid_entries.append(entry)
            continue
        residue, atoms = entry.split(":", 1)
        atom_text = _atom_list_text(atoms)
        if residue.strip() and atom_text:
            result[residue.strip()] = atom_text
        else:
            invalid_entries.append(entry)
    if invalid_entries:
        raise BackendError(
            make_error(
                "INVALID_PROTEIN_ATOM_SELECTION",
                "ProteinAtomSelector entries must look like A56:CG,OH.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                option_key="proteinAtoms",
                details={"invalid_entries": invalid_entries},
            )
        )
    return result


def _atom_list_text(value) -> str:
    if isinstance(value, list):
        atoms = [str(item).strip() for item in value if str(item).strip()]
    else:
        atoms = [item.strip() for item in str(value).split(",") if item.strip()]
    return ",".join(dict.fromkeys(atoms))


def _structure_payloads(inputs: dict[str, TypedPayload]) -> list[TypedPayload]:
    return [
        payload
        for payload in inputs.values()
        if payload.type_name in {"Ligand", "Batch Ligand", "Protein", "Batch Protein", "Batch Protein with Ligand", "Batch Protein (With Ligand)"}
    ]


def _validate_atoms_exist(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload], selected_atoms: list[str], field: str) -> None:
    contents = []
    for payload in _structure_payloads(inputs):
        contents.extend(read_payload_files(ctx, payload))
    if not contents:
        return
    available = set().union(*(set(list_atom_names(content)) for content in contents))
    missing = [atom for atom in selected_atoms if atom not in available]
    if missing:
        raise BackendError(
            make_error(
                "UNKNOWN_SELECTED_ATOM",
                f"Selected atom(s) are not present in the connected PDB input: {', '.join(missing)}.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                option_key=field,
                details={"missing_atoms": missing, "available_atoms": sorted(available)},
            )
        )


def _validate_residues_exist(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload], selected_residues: list[str], field: str) -> None:
    contents = []
    for payload in _structure_payloads(inputs):
        contents.extend(read_payload_files(ctx, payload))
    if not contents:
        return
    _validate_residues_in_contents(ctx, node, contents, selected_residues, field)


def _validate_residues_in_contents(ctx: ExecutionContext, node: WorkflowNode, contents: list[str], selected_residues: list[str], field: str) -> None:
    available = set().union(*(set(list_residue_ids(content)) for content in contents))
    missing = [residue for residue in selected_residues if residue not in available]
    if missing:
        raise BackendError(
            make_error(
                "UNKNOWN_SELECTED_RESIDUE",
                f"Selected residue(s) are not present in the connected PDB input: {', '.join(missing)}.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                option_key=field,
                details={"missing_residues": missing, "available_residues": sorted(available)},
            )
        )


def _validate_chains_exist(ctx: ExecutionContext, node: WorkflowNode, proteins: list[str], selected_chains: list[str]) -> None:
    available = set().union(*(set(list_chain_ids(content)) for content in proteins))
    missing = [chain for chain in selected_chains if chain not in available]
    if missing:
        raise BackendError(
            make_error(
                "UNKNOWN_SELECTED_CHAIN",
                f"Selected chain(s) are not present in the connected PDB input: {', '.join(missing)}.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                option_key="chains",
                details={"missing_chains": missing, "available_chains": sorted(available)},
            )
        )


def _validate_protein_atoms_exist(ctx: ExecutionContext, node: WorkflowNode, protein_files: list[str], selected: dict[str, str]) -> None:
    available: dict[str, set[str]] = {}
    for content in protein_files:
        for residue, atoms in residue_atom_map(content).items():
            available.setdefault(residue, set()).update(atoms)
    missing_residues = [residue for residue in selected if residue not in available]
    missing_atoms = {
        residue: [atom for atom in split_selector(atoms) if atom not in available.get(residue, set())]
        for residue, atoms in selected.items()
        if residue in available
    }
    missing_atoms = {residue: atoms for residue, atoms in missing_atoms.items() if atoms}
    if missing_residues or missing_atoms:
        raise BackendError(
            make_error(
                "UNKNOWN_SELECTED_PROTEIN_ATOM",
                "Selected protein atom(s) are not present in the connected PDB input.",
                run_id=ctx.run_id,
                node_id=node.id,
                node_type=node.type,
                option_key="proteinAtoms",
                details={
                    "missing_residues": missing_residues,
                    "missing_atoms": missing_atoms,
                    "available_residues": sorted(available),
                },
            )
        )
