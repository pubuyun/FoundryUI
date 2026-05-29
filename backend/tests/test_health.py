import asyncio

from backend.main import health, node_catalog
from backend.nodes.registry import node_for, registered_nodes


def test_health() -> None:
    assert asyncio.run(health()) == {"status": "ok"}


def test_node_catalog_exposes_manual_node_metadata() -> None:
    catalog = asyncio.run(node_catalog())
    atom_selector = next(node for node in catalog["nodes"] if node["type"] == "AtomSelector")
    assert atom_selector["requiresRuntimeInput"] is True
    assert atom_selector["ui"]["viewerMode"] == "atom"
    assert any(type_def["name"] == "Score" and type_def["color"] for type_def in catalog["types"])


def test_nodes_are_registered_from_classes() -> None:
    node_types = {node.type_name for node in registered_nodes()}
    assert {"LigandInput", "RosettaFold", "FilterAtomsChirality"} <= node_types
    assert node_for("LigandInput").spec.outputs["ligand"].type_name == "Ligand"
    assert node_for("LigandInput").upload_validation.missing_code == "MISSING_LIGAND_FILE"
