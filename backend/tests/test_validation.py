from backend.schemas.workflow import WorkflowGraph
from backend.workflow.validation import validate_workflow


def test_validate_rejects_disconnected_required_port() -> None:
    graph = WorkflowGraph.model_validate(
        {
            "nodes": [
                {
                    "id": "rf",
                    "type": "RosettaFold",
                    "inputs": {"sequences": {"type": "Batch Sequence"}},
                    "outputs": {"score": {"type": "Score"}},
                }
            ],
            "connections": [],
        }
    )

    errors = validate_workflow(graph)

    assert [error.code for error in errors] == ["DISCONNECTED_REQUIRED_PORT"]
    assert errors[0].node_id == "rf"
    assert errors[0].interface_key == "sequences"


def test_validate_allows_batch_structure_connection() -> None:
    graph = WorkflowGraph.model_validate(
        {
            "nodes": [
                {
                    "id": "protein",
                    "type": "ProteinInput",
                    "outputs": {"batchProtein": {"type": "Batch Protein"}},
                },
                {
                    "id": "viewer",
                    "type": "PDBViewer",
                    "inputs": {"structures": {"type": "Batch Structure"}},
                },
            ],
            "connections": [
                {
                    "from": {"nodeId": "protein", "key": "batchProtein", "type": "Batch Protein"},
                    "to": {"nodeId": "viewer", "key": "structures", "type": "Batch Structure"},
                }
            ],
        }
    )

    assert validate_workflow(graph) == []
