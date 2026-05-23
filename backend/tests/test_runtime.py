import asyncio

from backend.artifacts.registry import artifact_store
from backend.runtime.registry import run_registry
from backend.runtime.runner import run_workflow
from backend.schemas.workflow import RunCreateRequest


PDB = """ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 40.00           N
ATOM      2  CA  GLY A   1       1.000   0.000   0.000  1.00 40.00           C
ATOM      3  C   GLY A   1       1.000   1.000   0.000  1.00 40.00           C
ATOM      4  O   GLY A   1       1.000   1.500   1.000  1.00 40.00           O
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
