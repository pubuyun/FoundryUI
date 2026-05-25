from __future__ import annotations

import asyncio
import json

from backend.bio.pdb import filter_pdb_chains, filter_pdb_residues
from backend.nodes.common import ExecutionContext, node_dir, option, payload_from_artifacts, read_payload_files, split_selector
from backend.schemas.errors import BackendError, make_error
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def atom_selector(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    values = await _runtime_selector_values(ctx, node, inputs, "atoms") if inputs else {}
    atoms = split_selector(values.get("atoms", option(node, "atoms", "")))
    artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "atoms.json", atoms, "List of Atoms", item_count=len(atoms))
    return {"atoms": payload_from_artifacts("List of Atoms", [artifact], data=atoms)}


async def residue_selector(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    values = await _runtime_selector_values(ctx, node, inputs, "residues") if inputs else {}
    residues = split_selector(values.get("residues", option(node, "residues", "")))
    artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "residues.json", residues, "List of Residues", item_count=len(residues))
    return {"residues": payload_from_artifacts("List of Residues", [artifact], data=residues)}


async def protein_chain_selector(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    values = await _runtime_selector_values(ctx, node, inputs, "chains")
    chains = split_selector(values.get("chains", option(node, "chains", "")))
    if not chains:
        raise BackendError(make_error("MISSING_CHAIN_SELECTION", "ProteinChainSelector requires at least one selected chain.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="chains"))
    proteins = read_payload_files(ctx, inputs["batchProtein"])
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
    atoms = _parse_protein_atom_map(values.get("proteinAtoms", option(node, "proteinAtoms", "")))
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


def _parse_protein_atom_map(value) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(residue).strip(): _atom_list_text(atoms) for residue, atoms in value.items() if str(residue).strip() and _atom_list_text(atoms)}
    text = str(value or "").strip()
    if not text:
        return {}
    if text.startswith("{"):
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Protein atom selection JSON must be an object.")
        return _parse_protein_atom_map(data)
    result: dict[str, str] = {}
    for entry in [part.strip() for part in text.replace("\n", ";").split(";") if part.strip()]:
        if ":" not in entry:
            continue
        residue, atoms = entry.split(":", 1)
        atom_text = _atom_list_text(atoms)
        if residue.strip() and atom_text:
            result[residue.strip()] = atom_text
    return result


def _atom_list_text(value) -> str:
    if isinstance(value, list):
        atoms = [str(item).strip() for item in value if str(item).strip()]
    else:
        atoms = [item.strip() for item in str(value).split(",") if item.strip()]
    return ",".join(dict.fromkeys(atoms))
