import asyncio

from backend.artifacts.registry import artifact_store
from backend.runtime.registry import run_registry
from backend.schemas.payloads import TypedPayload
from backend.runtime.runner import run_workflow
from backend.schemas.workflow import RunCreateRequest
from backend.bio.sequences import pdb_to_sequence
from backend.bio.ligand import ligand_matches_smiles_chirality, smiles_to_pdb
from backend.nodes.common import ExecutionContext
from backend.nodes.filters import filter_chirality
from backend.schemas.workflow import WorkflowNode


PDB = """ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 40.00           N
ATOM      2  CA  GLY A   1       1.000   0.000   0.000  1.00 40.00           C
ATOM      3  C   GLY A   1       1.000   1.000   0.000  1.00 40.00           C
ATOM      4  O   GLY A   1       1.000   1.500   1.000  1.00 40.00           O
END
"""

LIGAND_ABC = """HETATM    1  C1  ABC A   1       0.000   0.000   0.000  1.00 10.00           C
END
"""

LIGAND_DEF = """HETATM    1  C1  DEF A   1       1.000   0.000   0.000  1.00 10.00           C
END
"""

def test_lightweight_run_writes_intermediate_artifact() -> None:
    async def execute() -> None:
        run_id = "run_test_lightweight"
        artifact_store.init_run(run_id)
        request = RunCreateRequest.model_validate(
            {
                "workflow": {
                    "nodes": [
                        {"id": "protein", "type": "ProteinInput", "outputs": {"batchProtein": {"type": "Batch Protein"}}},
                        {"id": "viewer", "type": "PDBViewer", "inputs": {"structures": {"type": "Batch Structure"}}},
                    ],
                    "connections": [
                        {
                            "from": {"nodeId": "protein", "key": "batchProtein", "type": "Batch Protein"},
                            "to": {"nodeId": "viewer", "key": "structures", "type": "Batch Structure"},
                        }
                    ],
                },
                "uploads": {"protein": [{"name": "protein.pdb", "type": "pdb", "content": PDB}]},
            }
        )
        await run_registry.create(run_id, total_nodes=2, request=request)
        await run_workflow(run_id, request)
        status = run_registry.status(run_id)
        assert status is not None
        assert status.state == "completed"
        artifacts = artifact_store.list_run(run_id)
        assert any(artifact.payload_type == "Batch Protein" for artifact in artifacts)

    asyncio.run(execute())


def test_run_registry_counts_node_completion_once() -> None:
    async def execute() -> None:
        run_id = "run_test_completion_count"
        await run_registry.create(run_id, total_nodes=1)
        await run_registry.set_node_completed(run_id, "node_a", "ProteinInput")
        await run_registry.set_node_completed(run_id, "node_a", "ProteinInput")
        status = run_registry.status(run_id)
        assert status is not None
        assert status.completed_nodes == 1
        assert status.progress_percent == 100

    asyncio.run(execute())


def test_unchanged_node_reuses_previous_run_output() -> None:
    async def execute() -> None:
        first_run_id = "run_test_cache_previous"
        second_run_id = "run_test_cache_current"
        workflow = {
            "nodes": [
                {"id": "protein", "type": "ProteinInput", "outputs": {"batchProtein": {"type": "Batch Protein"}}},
                {"id": "viewer", "type": "PDBViewer", "inputs": {"structures": {"type": "Batch Structure"}}},
            ],
            "connections": [
                {
                    "from": {"nodeId": "protein", "key": "batchProtein", "type": "Batch Protein"},
                    "to": {"nodeId": "viewer", "key": "structures", "type": "Batch Structure"},
                }
            ],
        }
        base_request = {
            "workflow": workflow,
            "uploads": {"protein": [{"name": "protein.pdb", "type": "pdb", "content": PDB}]},
        }
        first_request = RunCreateRequest.model_validate(base_request)
        artifact_store.init_run(first_run_id)
        await run_registry.create(first_run_id, total_nodes=2, request=first_request)
        await run_workflow(first_run_id, first_request)

        second_request = RunCreateRequest.model_validate({**base_request, "previous_run_id": first_run_id})
        artifact_store.init_run(second_run_id)
        await run_registry.create(second_run_id, total_nodes=2, request=second_request)
        await run_workflow(second_run_id, second_request)

        status = run_registry.status(second_run_id)
        assert status is not None
        assert status.state == "completed", status.errors[0]["message"] if status.errors else status.errors
        artifacts = [artifact for artifact in artifact_store.list_run(second_run_id) if artifact.payload_type == "Batch Protein"]
        assert any("_cached_" in artifact.path for artifact in artifacts)

    asyncio.run(execute())


def test_single_ligand_input_renames_residue() -> None:
    async def execute() -> None:
        run_id = "run_test_single_ligand_residue"
        artifact_store.init_run(run_id)
        request = RunCreateRequest.model_validate(
            {
                "workflow": {
                    "nodes": [{"id": "ligand", "type": "LigandInput", "options": {"source": "PDB"}, "outputs": {"ligand": {"type": "Ligand"}}}],
                    "connections": [],
                },
                "uploads": {"ligand": [{"name": "ligand.pdb", "type": "pdb", "content": LIGAND_ABC}]},
            }
        )
        await run_registry.create(run_id, total_nodes=1, request=request)
        await run_workflow(run_id, request)
        artifacts = artifact_store.list_run(run_id)
        ligand_artifact = next(artifact for artifact in artifacts if artifact.payload_type == "Ligand")
        content = artifact_store.absolute(run_id, ligand_artifact.path).read_text()
        assert " L:1 " in content
        assert " ABC " not in content

    asyncio.run(execute())


def test_batch_ligand_upload_does_not_rename_residues() -> None:
    async def execute() -> None:
        run_id = "run_test_batch_ligand_residue"
        artifact_store.init_run(run_id)
        request = RunCreateRequest.model_validate(
            {
                "workflow": {
                    "nodes": [{"id": "ligand", "type": "LigandInput", "options": {"source": "PDB"}, "outputs": {"ligand": {"type": "Ligand"}}}],
                    "connections": [],
                },
                "uploads": {
                    "ligand": [
                        {"name": "ligand_a.pdb", "type": "pdb", "content": LIGAND_ABC},
                        {"name": "ligand_b.pdb", "type": "pdb", "content": LIGAND_DEF},
                    ]
                },
            }
        )
        await run_registry.create(run_id, total_nodes=1, request=request)
        await run_workflow(run_id, request)
        artifacts = [artifact for artifact in artifact_store.list_run(run_id) if artifact.payload_type == "Batch Ligand"]
        contents = [artifact_store.absolute(run_id, artifact.path).read_text() for artifact in artifacts]
        assert len(contents) == 2
        assert " ABC " in contents[0]
        assert " DEF " in contents[1]
        assert all(" L:1 " not in content for content in contents)

    asyncio.run(execute())


def test_batch_ligand_first_promotes_residue_name_metadata() -> None:
    payload = TypedPayload(type_name="Batch Ligand", data=["a", "b"], paths=["a.pdb", "b.pdb"], metadata={"residue_names": ["ABC", "DEF"]})

    first = payload.first("Ligand")

    assert first.metadata["residue_name"] == "ABC"


def test_pdb_to_sequence_uses_standard_residue_codes() -> None:
    assert pdb_to_sequence(PDB) == "G"


def test_filter_chirality_keeps_only_matching_smiles_chirality() -> None:
    async def execute() -> None:
        run_id = "run_test_filter_by_ligand_match"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=1)
        node = WorkflowNode(id="filter", type="FilterChirality", options={"smiles": "F[C@](Cl)(Br)I"})
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        matching_ligand = smiles_to_pdb("F[C@](Cl)(Br)I")
        different_ligand = smiles_to_pdb("F[C@@](Cl)(Br)I")
        matching = artifact_store.write_text(run_id=run_id, path=root / "matching.pdb", content=PDB.replace("END\n", "") + matching_ligand, payload_type="Batch Protein (With Ligand)")
        different = artifact_store.write_text(run_id=run_id, path=root / "different.pdb", content=PDB.replace("END\n", "") + different_ligand, payload_type="Batch Protein (With Ligand)")

        result = await filter_chirality(
            ctx,
            node,
            {
                "complexes": TypedPayload(
                    type_name="Batch Protein (With Ligand)",
                    item_count=2,
                    paths=[matching.path, different.path],
                    data=[PDB + matching_ligand, PDB + different_ligand],
                ),
            },
        )

        assert result["complexes"].item_count == 1
        assert " CL1 " in result["complexes"].data[0]

    asyncio.run(execute())


def test_ligand_matches_smiles_chirality() -> None:
    ligand = smiles_to_pdb("F[C@](Cl)(Br)I")
    different_ligand = smiles_to_pdb("F[C@@](Cl)(Br)I")

    assert ligand_matches_smiles_chirality(ligand, "F[C@](Cl)(Br)I")
    assert not ligand_matches_smiles_chirality(different_ligand, "F[C@](Cl)(Br)I")
