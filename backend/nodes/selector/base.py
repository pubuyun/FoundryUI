import asyncio
import json

from backend.bio.pdb import list_atom_names, list_chain_ids, list_residue_ids, residue_atom_map
from backend.nodes.common import option, read_payload_files, split_selector
from backend.nodes.registry import FoundryNode
from backend.schemas.errors import BackendError, make_error


class SelectorNode(FoundryNode):
    category = "Selector"

    @staticmethod
    async def runtime_selector_values(ctx, node, inputs, field: str) -> dict:
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
            return await ctx.registry.request_node_input(ctx.run_id, node.id, node.type, [field], payloads, {field: option(node, field, "")})
        except asyncio.CancelledError as exc:
            raise BackendError(make_error("RUN_CANCELLED", "Run was stopped while waiting for selector input.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, recoverable=True)) from exc

    @staticmethod
    def residue_values(payload) -> list[str]:
        if payload is None:
            return []
        if isinstance(payload.data, list):
            return [str(item).strip() for item in payload.data if str(item).strip()]
        if isinstance(payload.data, str):
            return split_selector(payload.data)
        return []

    @classmethod
    def parse_protein_atom_map(cls, ctx, node, value) -> dict[str, str]:
        if isinstance(value, dict):
            return {str(residue).strip(): cls.atom_list_text(atoms) for residue, atoms in value.items() if str(residue).strip() and cls.atom_list_text(atoms)}
        text = str(value or "").strip()
        if not text:
            return {}
        if text.startswith("{"):
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise BackendError(make_error("INVALID_PROTEIN_ATOM_SELECTION", "ProteinAtomSelector atom selection JSON is not valid.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="proteinAtoms", details={"selection": text})) from exc
            if not isinstance(data, dict):
                raise BackendError(make_error("INVALID_PROTEIN_ATOM_SELECTION", "ProteinAtomSelector atom selection JSON must be an object mapping residues to atom names.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="proteinAtoms", details={"selection": text}))
            return cls.parse_protein_atom_map(ctx, node, data)
        result: dict[str, str] = {}
        invalid_entries: list[str] = []
        for entry in [part.strip() for part in text.replace("\n", ";").split(";") if part.strip()]:
            if ":" not in entry:
                invalid_entries.append(entry)
                continue
            residue, atoms = entry.split(":", 1)
            atom_text = cls.atom_list_text(atoms)
            if residue.strip() and atom_text:
                result[residue.strip()] = atom_text
            else:
                invalid_entries.append(entry)
        if invalid_entries:
            raise BackendError(make_error("INVALID_PROTEIN_ATOM_SELECTION", "ProteinAtomSelector entries must look like A56:CG,OH.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="proteinAtoms", details={"invalid_entries": invalid_entries}))
        return result

    @staticmethod
    def atom_list_text(value) -> str:
        if isinstance(value, list):
            atoms = [str(item).strip() for item in value if str(item).strip()]
        else:
            atoms = [item.strip() for item in str(value).split(",") if item.strip()]
        return ",".join(dict.fromkeys(atoms))

    @staticmethod
    def structure_payloads(inputs) -> list:
        return [
            payload
            for payload in inputs.values()
            if payload.type_name in {"Ligand", "Batch Ligand", "Protein", "Batch Protein", "Batch Protein with Ligand", "Batch Protein (With Ligand)"}
        ]

    @classmethod
    def validate_atoms_exist(cls, ctx, node, inputs, selected_atoms: list[str], field: str) -> None:
        contents = []
        for payload in cls.structure_payloads(inputs):
            contents.extend(read_payload_files(ctx, payload))
        if not contents:
            return
        available = set().union(*(set(list_atom_names(content)) for content in contents))
        missing = [atom for atom in selected_atoms if atom not in available]
        if missing:
            raise BackendError(make_error("UNKNOWN_SELECTED_ATOM", f"Selected atom(s) are not present in the connected PDB input: {', '.join(missing)}.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key=field, details={"missing_atoms": missing, "available_atoms": sorted(available)}))

    @classmethod
    def validate_residues_exist(cls, ctx, node, inputs, selected_residues: list[str], field: str) -> None:
        contents = []
        for payload in cls.structure_payloads(inputs):
            contents.extend(read_payload_files(ctx, payload))
        if contents:
            cls.validate_residues_in_contents(ctx, node, contents, selected_residues, field)

    @staticmethod
    def validate_residues_in_contents(ctx, node, contents: list[str], selected_residues: list[str], field: str) -> None:
        available = set().union(*(set(list_residue_ids(content)) for content in contents))
        missing = [residue for residue in selected_residues if residue not in available]
        if missing:
            raise BackendError(make_error("UNKNOWN_SELECTED_RESIDUE", f"Selected residue(s) are not present in the connected PDB input: {', '.join(missing)}.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key=field, details={"missing_residues": missing, "available_residues": sorted(available)}))

    @staticmethod
    def validate_chains_exist(ctx, node, proteins: list[str], selected_chains: list[str]) -> None:
        available = set().union(*(set(list_chain_ids(content)) for content in proteins))
        missing = [chain for chain in selected_chains if chain not in available]
        if missing:
            raise BackendError(make_error("UNKNOWN_SELECTED_CHAIN", f"Selected chain(s) are not present in the connected PDB input: {', '.join(missing)}.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="chains", details={"missing_chains": missing, "available_chains": sorted(available)}))

    @staticmethod
    def validate_protein_atoms_exist(ctx, node, protein_files: list[str], selected: dict[str, str]) -> None:
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
            raise BackendError(make_error("UNKNOWN_SELECTED_PROTEIN_ATOM", "Selected protein atom(s) are not present in the connected PDB input.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="proteinAtoms", details={"missing_residues": missing_residues, "missing_atoms": missing_atoms, "available_residues": sorted(available)}))
