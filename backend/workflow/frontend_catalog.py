from __future__ import annotations

from typing import Any

from backend.nodes.registry import registered_nodes


TYPE_DETAILS = [
    {"name": "Ligand", "detail": "Single small-molecule PDB payload", "color": "#249a86"},
    {"name": "Protein", "detail": "Single protein PDB payload", "color": "#4678d4"},
    {"name": "List of Residues", "detail": 'Residue ids such as "A58,A103"', "color": "#9062ce"},
    {"name": "List of Atoms", "detail": 'Ligand atom ids such as "C1,O2"', "color": "#e2559b"},
    {"name": "Residues Atoms List", "detail": "Residue-to-atom selections", "color": "#b36b2c"},
    {"name": "Batch Protein", "detail": "Protein model collection", "color": "#2368ad"},
    {"name": "Batch Ligand", "detail": "Ligand conformer collection", "color": "#168b69"},
    {"name": "Batch Protein with Ligand", "detail": "Strict protein-ligand complex collection", "color": "#c74b67"},
    {"name": "Batch Protein (With Ligand)", "detail": "Protein or protein-ligand complex collection", "color": "#c74b67"},
    {"name": "Batch Sequence", "detail": "Sequence collection from FASTA or design output", "color": "#7d8b23"},
    {"name": "Score", "detail": "List of score dictionaries from folding/filtering", "color": "#d28a19"},
]

TYPE_CONVERSIONS = [
    {"from": "Protein", "to": "Batch Protein"},
    {"from": "Ligand", "to": "Batch Ligand"},
    {"from": "Batch Protein with Ligand", "to": "Batch Protein (With Ligand)"},
    {"from": "Batch Protein (With Ligand)", "to": "Batch Protein with Ligand"},
    {"from": "Batch Protein with Ligand", "to": "Batch Protein"},
    {"from": "Batch Protein (With Ligand)", "to": "Batch Protein"},
    {"from": "Batch Protein", "to": "Batch Protein (With Ligand)"},
    {"from": "Batch Ligand", "to": "Ligand"},
    {"from": "Batch Protein", "to": "Protein"},
    {"from": "Batch Protein with Ligand", "to": "Protein"},
    {"from": "Batch Protein (With Ligand)", "to": "Protein"},
    {"from": "Ligand", "to": "Batch Protein (With Ligand)"},
    {"from": "Batch Ligand", "to": "Batch Protein (With Ligand)"},
    {"from": "Protein", "to": "Batch Protein (With Ligand)"},
]


def frontend_node_catalog() -> dict[str, Any]:
    nodes = [node.frontend_catalog_entry() for node in registered_nodes()]
    return {"version": 1, "types": TYPE_DETAILS, "conversions": TYPE_CONVERSIONS, "nodes": nodes}
