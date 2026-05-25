import asyncio
import os
import signal
import sys

from backend.artifacts.registry import artifact_store
from backend.runtime.registry import run_registry
from backend.schemas.payloads import TypedPayload
from backend.runtime.runner import run_workflow
from backend.runtime.subprocesses import run_command_streaming
from backend.schemas.workflow import RunCreateRequest
from backend.workflow.ryvencore_adapter import _node_cache_key, _reuse_cached_outputs
from backend.bio.sequences import pdb_to_sequence
from backend.bio.ligand import ligand_matches_smiles_chirality, smiles_to_pdb
from backend.nodes.common import ExecutionContext
from backend.nodes import folding as folding_module
from backend.nodes.filters import filter_atoms_chirality, filter_by_score, filter_chirality
from backend.nodes.folding import rosetta_fold
from backend.nodes.generation import rfdiffusion_enzyme, rfdiffusion_protein_binder
from backend.nodes.scoring import calculate_ligand_rmsd, calculate_protein_rmsd
from backend.nodes.selectors import protein_atom_selector, protein_chain_selector
from backend.nodes.utils import merge
from backend.schemas.workflow import WorkflowNode


PDB = """ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 40.00           N
ATOM      2  CA  GLY A   1       1.000   0.000   0.000  1.00 40.00           C
ATOM      3  C   GLY A   1       1.000   1.000   0.000  1.00 40.00           C
ATOM      4  O   GLY A   1       1.000   1.500   1.000  1.00 40.00           O
END
"""

PDB_CHAIN_B = """ATOM      1  N   GLY B   2       0.000   0.000   0.000  1.00 40.00           N
ATOM      2  CA  GLY B   2       1.000   0.000   0.000  1.00 40.00           C
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


def test_filter_atoms_chirality_waits_for_targets_and_filters() -> None:
    async def execute() -> None:
        run_id = "run_test_filter_atoms_chirality"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=1)
        node = WorkflowNode(id="filter_atoms", type="FilterAtomsChirality", options={})
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        matching_ligand = smiles_to_pdb("F[C@](Cl)(Br)I")
        different_ligand = smiles_to_pdb("F[C@@](Cl)(Br)I")
        matching = artifact_store.write_text(run_id=run_id, path=root / "matching_atoms.pdb", content=PDB.replace("END\n", "") + matching_ligand, payload_type="Batch Protein (With Ligand)")
        different = artifact_store.write_text(run_id=run_id, path=root / "different_atoms.pdb", content=PDB.replace("END\n", "") + different_ligand, payload_type="Batch Protein (With Ligand)")

        task = asyncio.create_task(
            filter_atoms_chirality(
                ctx,
                node,
                {
                    "complexes": TypedPayload(
                        type_name="Batch Protein (With Ligand)",
                        item_count=2,
                        artifact_ids=[matching.artifact_id, different.artifact_id],
                        paths=[matching.path, different.path],
                        data=[PDB + matching_ligand, PDB + different_ligand],
                    ),
                },
            )
        )
        for _ in range(20):
            if run_registry.get(run_id).pending_inputs:
                break
            await asyncio.sleep(0.01)
        assert await run_registry.submit_node_input(run_id, "filter_atoms", {"chiralityTargets": "C1:S"})
        result = await task

        assert result["complexes"].item_count == 1
        assert " CL1 " in result["complexes"].data[0]

    asyncio.run(execute())


def test_ligand_matches_smiles_chirality() -> None:
    ligand = smiles_to_pdb("F[C@](Cl)(Br)I")
    different_ligand = smiles_to_pdb("F[C@@](Cl)(Br)I")

    assert ligand_matches_smiles_chirality(ligand, "F[C@](Cl)(Br)I")
    assert not ligand_matches_smiles_chirality(different_ligand, "F[C@](Cl)(Br)I")


def test_protein_atom_selector_waits_and_writes_atom_map() -> None:
    async def execute() -> None:
        run_id = "run_test_protein_atom_selector"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=1)
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        node = WorkflowNode(id="protein_atoms", type="ResidueAtomSelector", options={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        protein_artifact = artifact_store.write_text(run_id=run_id, path=root / "protein.pdb", content=PDB, payload_type="Protein")
        task = asyncio.create_task(
            protein_atom_selector(
                ctx,
                node,
                {
                    "residues": TypedPayload(type_name="List of Residues", item_count=1, data=["A1"]),
                    "protein": TypedPayload(type_name="Protein", item_count=1, artifact_ids=[protein_artifact.artifact_id], paths=[protein_artifact.path], data=PDB),
                },
            )
        )
        for _ in range(20):
            if run_registry.get(run_id).pending_inputs:
                break
            await asyncio.sleep(0.01)
        assert await run_registry.submit_node_input(run_id, "protein_atoms", {"proteinAtoms": '{"A1": "CA,O"}'})
        result = await task

        assert result["proteinAtoms"].type_name == "Residues Atoms List"
        assert result["proteinAtoms"].data == {"A1": "CA,O"}

    asyncio.run(execute())


def test_protein_chain_selector_filters_selected_chains() -> None:
    async def execute() -> None:
        run_id = "run_test_protein_chain_selector"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=1)
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        node = WorkflowNode(id="chain_selector", type="ChainFilter", options={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        protein = PDB.replace("END\n", "") + PDB_CHAIN_B
        artifact = artifact_store.write_text(run_id=run_id, path=root / "protein.pdb", content=protein, payload_type="Batch Protein")
        task = asyncio.create_task(
            protein_chain_selector(
                ctx,
                node,
                {"batchProtein": TypedPayload(type_name="Batch Protein", item_count=1, artifact_ids=[artifact.artifact_id], paths=[artifact.path], data=[protein])},
            )
        )
        for _ in range(20):
            if run_registry.get(run_id).pending_inputs:
                break
            await asyncio.sleep(0.01)
        assert await run_registry.submit_node_input(run_id, "chain_selector", {"chains": "B"})
        result = await task

        assert " B   2" in result["batchProtein"].data[0]
        assert " A   1" not in result["batchProtein"].data[0]

    asyncio.run(execute())


def test_manual_node_reuses_cache_when_inputs_unchanged() -> None:
    async def execute() -> None:
        first_run_id = "run_test_manual_cache_first"
        second_run_id = "run_test_manual_cache_second"
        protein = PDB.replace("END\n", "") + PDB_CHAIN_B
        request = RunCreateRequest.model_validate({"workflow": {"nodes": []}})
        node = WorkflowNode(id="chain_filter", type="ChainFilter", options={"chains": "B"})
        artifact_store.init_run(first_run_id)
        await run_registry.create(first_run_id, total_nodes=1, request=request)
        ctx = ExecutionContext(run_id=first_run_id, store=artifact_store, registry=run_registry, uploads={})
        root = artifact_store.node_dir(first_run_id, "source", "Test")
        source = artifact_store.write_text(run_id=first_run_id, path=root / "protein.pdb", content=protein, payload_type="Batch Protein")
        inputs = {"batchProtein": TypedPayload(type_name="Batch Protein", item_count=1, artifact_ids=[source.artifact_id], paths=[source.path], data=[protein])}
        cache_key = _node_cache_key(node, inputs, {})
        task = asyncio.create_task(protein_chain_selector(ctx, node, inputs))
        for _ in range(50):
            if run_registry.get(first_run_id).pending_inputs:
                break
            await asyncio.sleep(0.01)
        assert await run_registry.submit_node_input(first_run_id, "chain_filter", {"chains": "B"})
        result = await task
        await run_registry.record_output(first_run_id, "chain_filter", "batchProtein", result["batchProtein"])
        await run_registry.record_node_cache_key(first_run_id, "chain_filter", cache_key)

        second_request = RunCreateRequest.model_validate({"workflow": {"nodes": []}, "previous_run_id": first_run_id})
        artifact_store.init_run(second_run_id)
        await run_registry.create(second_run_id, total_nodes=1, request=second_request)
        second_ctx = ExecutionContext(run_id=second_run_id, store=artifact_store, registry=run_registry, uploads={})
        cached = await _reuse_cached_outputs(second_ctx, node, ["batchProtein"], cache_key)

        assert cached is not None
        assert cached["batchProtein"].type_name == "Batch Protein"
        assert not run_registry.get(second_run_id).pending_inputs

    asyncio.run(execute())


def test_merge_single_to_batch_rechains_structures() -> None:
    async def execute() -> None:
        run_id = "run_test_merge_single_to_batch"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=1)
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        protein_a = artifact_store.write_text(run_id=run_id, path=root / "a.pdb", content=PDB, payload_type="Batch Protein")
        protein_b = artifact_store.write_text(run_id=run_id, path=root / "b.pdb", content=PDB_CHAIN_B, payload_type="Batch Protein")
        ligand = artifact_store.write_text(run_id=run_id, path=root / "ligand.pdb", content=LIGAND_ABC, payload_type="Ligand")
        result = await merge(
            ctx,
            WorkflowNode(id="merge", type="Merge"),
            {
                "inputA": TypedPayload(type_name="Batch Protein", item_count=2, paths=[protein_a.path, protein_b.path], data=[PDB, PDB_CHAIN_B]),
                "inputB": TypedPayload(type_name="Ligand", item_count=1, paths=[ligand.path], data=LIGAND_ABC),
            },
        )

        assert result["complexes"].item_count == 2
        assert result["complexes"].type_name == "Batch Protein (With Ligand)"
        assert " A   1" in result["complexes"].data[0]
        assert " B   1" in result["complexes"].data[0]

    asyncio.run(execute())


def test_filter_by_score_waits_for_metric_choice() -> None:
    async def execute() -> None:
        run_id = "run_test_filter_by_score_runtime"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=1)
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        protein_a = artifact_store.write_text(run_id=run_id, path=root / "a.pdb", content=PDB, payload_type="Batch Protein")
        protein_b = artifact_store.write_text(run_id=run_id, path=root / "b.pdb", content=PDB_CHAIN_B, payload_type="Batch Protein")
        task = asyncio.create_task(
            filter_by_score(
                ctx,
                WorkflowNode(id="score_filter", type="FilterByScore", options={"mode": "Greater than", "threshold": 2}),
                {
                    "structures": TypedPayload(type_name="Batch Protein", item_count=2, paths=[protein_a.path, protein_b.path], data=[PDB, PDB_CHAIN_B]),
                    "score": TypedPayload(type_name="Score", item_count=2, data={"scores": [{"rmsd": 1.0}, {"rmsd": 3.0}]}),
                },
            )
        )
        for _ in range(20):
            if run_registry.get(run_id).pending_inputs:
                break
            await asyncio.sleep(0.01)
        assert await run_registry.submit_node_input(run_id, "score_filter", {"metric": "rmsd"})
        result = await task

        assert result["structures"].item_count == 1
        assert result["score"].data == [{"rmsd": 3.0}]

    asyncio.run(execute())


def test_rosetta_fold_cofold_builds_parallel_components(monkeypatch) -> None:
    async def execute() -> None:
        run_id = "run_test_rf3_cofold"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=1)
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        ligand_artifact = artifact_store.write_text(run_id=run_id, path=root / "ligand.pdb", content=LIGAND_ABC, payload_type="Batch Ligand")
        output_path = root / "rf3_output.pdb"
        output_path.write_text(PDB)
        captured: dict[str, object] = {}

        async def fake_run_rf3_fold(**kwargs):
            captured.update(kwargs)
            return [output_path], [{"pLDDT": 0.9, "length": 6}]

        monkeypatch.setattr(folding_module, "run_rf3_fold", fake_run_rf3_fold)
        result = await rosetta_fold(
            ctx,
            WorkflowNode(id="rf3", type="RosettaFold", options={"inputMode": "Co-folding"}),
            {
                "sequences": TypedPayload(
                    type_name="Batch Sequence",
                    item_count=2,
                    data=[{"id": "a", "sequence": "AAA"}, {"id": "b", "sequence": "BBB"}],
                ),
                "ligand": TypedPayload(
                    type_name="Batch Ligand",
                    item_count=2,
                    paths=[ligand_artifact.path],
                    data=[LIGAND_ABC],
                    metadata={"smiles_list": ["C", "CC"]},
                ),
            },
        )

        assert captured["cofold_jobs"] == [
            [{"seq": "AAA", "chain_id": "A"}, {"smiles": "C"}],
            [{"seq": "BBB", "chain_id": "A"}, {"smiles": "CC"}],
        ]
        assert result["structures"].type_name == "Batch Protein (With Ligand)"

    asyncio.run(execute())


def test_rosetta_fold_cofold_reuses_single_ligand_for_each_job(monkeypatch) -> None:
    async def execute() -> None:
        run_id = "run_test_rf3_cofold_single_ligand"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=1)
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        ligand_artifact = artifact_store.write_text(run_id=run_id, path=root / "ligand.pdb", content=LIGAND_ABC, payload_type="Ligand")
        output_a = root / "rf3_output_a.pdb"
        output_b = root / "rf3_output_b.pdb"
        output_a.write_text(PDB)
        output_b.write_text(PDB_CHAIN_B)
        captured: dict[str, object] = {}

        async def fake_run_rf3_fold(**kwargs):
            captured.update(kwargs)
            return [output_a, output_b], [{"pLDDT": 0.9, "length": 3}, {"pLDDT": 0.8, "length": 3}]

        monkeypatch.setattr(folding_module, "run_rf3_fold", fake_run_rf3_fold)
        await rosetta_fold(
            ctx,
            WorkflowNode(id="rf3", type="RosettaFold", options={"inputMode": "Co-folding"}),
            {
                "sequences": TypedPayload(
                    type_name="Batch Sequence",
                    item_count=2,
                    data=[{"id": "a", "sequence": "AAA"}, {"id": "b", "sequence": "BBB"}],
                ),
                "ligand": TypedPayload(
                    type_name="Ligand",
                    item_count=1,
                    paths=[ligand_artifact.path],
                    data=LIGAND_ABC,
                    metadata={"smiles": "C"},
                ),
            },
        )

        assert captured["cofold_jobs"] == [
            [{"seq": "AAA", "chain_id": "A"}, {"smiles": "C"}],
            [{"seq": "BBB", "chain_id": "A"}, {"smiles": "C"}],
        ]

    asyncio.run(execute())


def test_rosetta_fold_cofold_reuses_multiple_single_ligand_inputs(monkeypatch) -> None:
    async def execute() -> None:
        run_id = "run_test_rf3_cofold_multiple_single_ligands"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=1)
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        output_a = root / "rf3_output_a.pdb"
        output_b = root / "rf3_output_b.pdb"
        output_a.write_text(PDB)
        output_b.write_text(PDB_CHAIN_B)
        ligand_a = TypedPayload(type_name="Ligand", item_count=1, data=LIGAND_ABC, metadata={"smiles": "C"})
        ligand_b = TypedPayload(type_name="Ligand", item_count=1, data=LIGAND_DEF, metadata={"smiles": "CC"})
        captured: dict[str, object] = {}

        async def fake_run_rf3_fold(**kwargs):
            captured.update(kwargs)
            return [output_a, output_b], [{"pLDDT": 0.9, "length": 3}, {"pLDDT": 0.8, "length": 3}]

        monkeypatch.setattr(folding_module, "run_rf3_fold", fake_run_rf3_fold)
        await rosetta_fold(
            ctx,
            WorkflowNode(id="rf3", type="RosettaFold", options={"inputMode": "Co-folding"}),
            {
                "sequences": TypedPayload(
                    type_name="Batch Sequence",
                    item_count=2,
                    data=[{"id": "a", "sequence": "AAA"}, {"id": "b", "sequence": "BBB"}],
                ),
                "ligand": TypedPayload(
                    type_name="Ligand",
                    item_count=2,
                    data=[LIGAND_ABC, LIGAND_DEF],
                    metadata={"combined_payloads": [ligand_a.model_dump(), ligand_b.model_dump()]},
                ),
            },
        )

        assert captured["cofold_jobs"] == [
            [{"seq": "AAA", "chain_id": "A"}, {"smiles": "C"}, {"smiles": "CC"}],
            [{"seq": "BBB", "chain_id": "A"}, {"smiles": "C"}, {"smiles": "CC"}],
        ]

    asyncio.run(execute())


def test_rosetta_fold_cofold_pairs_multiple_sequence_inputs(monkeypatch) -> None:
    async def execute() -> None:
        run_id = "run_test_rf3_cofold_parallel_sequences"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=1)
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        output_a = root / "rf3_output_a.pdb"
        output_b = root / "rf3_output_b.pdb"
        output_a.write_text(PDB)
        output_b.write_text(PDB_CHAIN_B)
        source_a = TypedPayload(type_name="Batch Sequence", item_count=2, data=[{"id": "a1", "sequence": "AAA"}, {"id": "a2", "sequence": "AAB"}])
        source_b = TypedPayload(type_name="Batch Sequence", item_count=2, data=[{"id": "b1", "sequence": "BBB"}, {"id": "b2", "sequence": "BBC"}])
        captured: dict[str, object] = {}

        async def fake_run_rf3_fold(**kwargs):
            captured.update(kwargs)
            return [output_a, output_b], [{"pLDDT": 0.9, "length": 6}, {"pLDDT": 0.8, "length": 6}]

        monkeypatch.setattr(folding_module, "run_rf3_fold", fake_run_rf3_fold)
        await rosetta_fold(
            ctx,
            WorkflowNode(id="rf3", type="RosettaFold", options={"inputMode": "Co-folding"}),
            {
                "sequences": TypedPayload(
                    type_name="Batch Sequence",
                    item_count=4,
                    data=[*source_a.data, *source_b.data],
                    metadata={"combined_payloads": [source_a.model_dump(), source_b.model_dump()]},
                ),
            },
        )

        assert captured["cofold_jobs"] == [
            [{"seq": "AAA", "chain_id": "A"}, {"seq": "BBB", "chain_id": "B"}],
            [{"seq": "AAB", "chain_id": "A"}, {"seq": "BBC", "chain_id": "B"}],
        ]

    asyncio.run(execute())


def test_rosetta_fold_cofold_broadcasts_singleton_sequence_input(monkeypatch) -> None:
    async def execute() -> None:
        run_id = "run_test_rf3_cofold_singleton_sequence"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=1)
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        output_a = root / "rf3_output_a.pdb"
        output_b = root / "rf3_output_b.pdb"
        output_a.write_text(PDB)
        output_b.write_text(PDB_CHAIN_B)
        source_a = TypedPayload(type_name="Batch Sequence", item_count=1, data=[{"id": "a1", "sequence": "AAA"}])
        source_b = TypedPayload(type_name="Batch Sequence", item_count=2, data=[{"id": "b1", "sequence": "BBB"}, {"id": "b2", "sequence": "BBC"}])
        captured: dict[str, object] = {}

        async def fake_run_rf3_fold(**kwargs):
            captured.update(kwargs)
            return [output_a, output_b], [{"pLDDT": 0.9, "length": 6}, {"pLDDT": 0.8, "length": 6}]

        monkeypatch.setattr(folding_module, "run_rf3_fold", fake_run_rf3_fold)
        await rosetta_fold(
            ctx,
            WorkflowNode(id="rf3", type="RosettaFold", options={"inputMode": "Co-folding"}),
            {
                "sequences": TypedPayload(
                    type_name="Batch Sequence",
                    item_count=3,
                    data=[*source_a.data, *source_b.data],
                    metadata={"combined_payloads": [source_a.model_dump(), source_b.model_dump()]},
                ),
            },
        )

        assert captured["cofold_jobs"] == [
            [{"seq": "AAA", "chain_id": "A"}, {"seq": "BBB", "chain_id": "B"}],
            [{"seq": "AAA", "chain_id": "A"}, {"seq": "BBC", "chain_id": "B"}],
        ]

    asyncio.run(execute())


def test_calculate_rmsd_nodes_emit_scores() -> None:
    async def execute() -> None:
        run_id = "run_test_rmsd_nodes"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=2)
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        ref_protein = artifact_store.write_text(run_id=run_id, path=root / "ref.pdb", content=PDB, payload_type="Protein")
        batch_protein = artifact_store.write_text(run_id=run_id, path=root / "protein.pdb", content=PDB, payload_type="Batch Protein")
        ref_ligand = artifact_store.write_text(run_id=run_id, path=root / "ligand_ref.pdb", content=LIGAND_ABC, payload_type="Ligand")
        batch_ligand = artifact_store.write_text(run_id=run_id, path=root / "ligand.pdb", content=LIGAND_ABC, payload_type="Batch Ligand")
        protein_result = await calculate_protein_rmsd(
            ctx,
            WorkflowNode(id="protein_rmsd", type="CalculateProteinRMSD"),
            {
                "reference": TypedPayload(type_name="Protein", item_count=1, paths=[ref_protein.path], data=PDB),
                "batchProtein": TypedPayload(type_name="Batch Protein", item_count=1, paths=[batch_protein.path], data=[PDB]),
            },
        )
        ligand_result = await calculate_ligand_rmsd(
            ctx,
            WorkflowNode(id="ligand_rmsd", type="CalculateLigandRMSD"),
            {
                "reference": TypedPayload(type_name="Ligand", item_count=1, paths=[ref_ligand.path], data=LIGAND_ABC),
                "ligands": TypedPayload(type_name="Batch Ligand", item_count=1, paths=[batch_ligand.path], data=[LIGAND_ABC]),
            },
        )

        assert protein_result["score"].data == [{"protein_rmsd": 0.0}]
        assert ligand_result["score"].data == [{"ligand_rmsd": 0.0}]

    asyncio.run(execute())


def test_rfdiffusion_nodes_build_expected_json(monkeypatch) -> None:
    async def execute() -> None:
        run_id = "run_test_rfd3_json"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=2)
        ctx = ExecutionContext(run_id=run_id, store=artifact_store, registry=run_registry, uploads={})
        root = artifact_store.node_dir(run_id, "source", "Test")
        protein = artifact_store.write_text(run_id=run_id, path=root / "protein.pdb", content=PDB, payload_type="Protein")
        complex_artifact = artifact_store.write_text(run_id=run_id, path=root / "complex.pdb", content=PDB + LIGAND_ABC, payload_type="Batch Protein with Ligand")
        captured = []

        async def fake_run_rfd3_payload(**kwargs):
            captured.append(kwargs["payload"])
            output = kwargs["work_dir"] / "fake_output.pdb"
            output.write_text(PDB)
            return [output]

        monkeypatch.setattr("backend.nodes.generation.run_rfd3_payload", fake_run_rfd3_payload)
        await rfdiffusion_protein_binder(
            ctx,
            WorkflowNode(id="binder", type="RFDiffusionProteinBinder", options={"contig": "40-120,/0,E6-155"}),
            {
                "protein": TypedPayload(type_name="Protein", item_count=1, paths=[protein.path], data=PDB),
                "selectHotspots": TypedPayload(type_name="Residues Atoms List", data={"E64": "CD2,CZ"}),
            },
        )
        await rfdiffusion_enzyme(
            ctx,
            WorkflowNode(id="enzyme", type="RFDiffusionEnzyme", options={"length": "180-200"}),
            {
                "complex": TypedPayload(type_name="Batch Protein with Ligand", item_count=1, paths=[complex_artifact.path], data=[PDB + LIGAND_ABC]),
                "ligand": TypedPayload(type_name="List of Residues", data=["ABC"]),
                "unindex": TypedPayload(type_name="List of Residues", data=["A1"]),
                "selectFixedAtoms": TypedPayload(type_name="Residues Atoms List", data={"A1": "CA"}),
                "selectBuried": TypedPayload(type_name="Residues Atoms List", data={"ABC": "C1"}),
                "selectExposed": TypedPayload(type_name="Residues Atoms List", data={"ABC": ""}),
            },
        )

        assert captured[0]["foundryui_protein_binder"]["select_hotspots"] == {"E64": "CD2,CZ"}
        assert captured[0]["foundryui_protein_binder"]["infer_ori_strategy"] == "hotspots"
        assert captured[1]["foundryui_enzyme"]["ligand"] == "ABC"
        assert captured[1]["foundryui_enzyme"]["select_fixed_atoms"] == {"A1": "CA"}

    asyncio.run(execute())


def test_subprocess_stop_kills_child_process_group() -> None:
    async def execute() -> None:
        run_id = "run_test_stop_process_group"
        artifact_store.init_run(run_id)
        await run_registry.create(run_id, total_nodes=1)
        marker = artifact_store.run_dir(run_id) / "child.pid"
        script = (
            "import os, signal, subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            f"open({str(marker)!r}, 'w').write(str(child.pid))\n"
            "sys.stdout.write('started\\n'); sys.stdout.flush()\n"
            "time.sleep(60)\n"
        )
        task = asyncio.create_task(
            run_command_streaming(
                command=[sys.executable, "-c", script],
                cwd=artifact_store.run_dir(run_id),
                run_id=run_id,
                node_id="cmd",
                node_type="TestCommand",
                registry=run_registry,
                store=artifact_store,
            )
        )
        for _ in range(100):
            if marker.exists():
                break
            await asyncio.sleep(0.01)
        assert marker.exists()
        child_pid = int(marker.read_text())
        assert await run_registry.request_cancel(run_id)
        try:
            await task
        except Exception as exc:
            assert getattr(exc, "error").code == "RUN_CANCELLED"
        await asyncio.sleep(0.1)
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            return
        os.kill(child_pid, signal.SIGKILL)
        raise AssertionError("child process survived run cancellation")

    asyncio.run(execute())
