from backend.schemas.workflow import WorkflowGraph
from backend.schemas.workflow import RunCreateRequest
from backend.main import _validate_run_uploads
from backend.workflow.type_conversions import is_assignable
from backend.workflow.validation import validate_workflow


VALID_LIGAND_PDB = """HETATM    1  C1  LIG A   1       0.000   0.000   0.000  1.00 20.00           C
END
"""


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


def test_validate_allows_flexible_complex_to_strict_complex_connection() -> None:
    assert is_assignable("Batch Protein (With Ligand)", "Batch Protein with Ligand")
    assert is_assignable("Ligand", "Batch Ligand")


def test_validate_allows_blank_filter_by_score_metric_until_runtime() -> None:
    graph = WorkflowGraph.model_validate(
        {
            "nodes": [
                {
                    "id": "filter",
                    "type": "FilterByScore",
                    "inputs": {
                        "structures": {"type": "Batch Protein (With Ligand)"},
                        "score": {"type": "Score"},
                    },
                    "options": {"metric": "", "mode": "Is largest top", "threshold": 10},
                    "outputs": {
                        "structures": {"type": "Batch Protein (With Ligand)"},
                        "score": {"type": "Score"},
                    },
                },
                {
                    "id": "viewer",
                    "type": "PDBViewer",
                    "inputs": {"structures": {"type": "Batch Structure"}},
                },
            ],
            "connections": [
                {
                    "from": {"nodeId": "filter", "key": "structures", "type": "Batch Protein (With Ligand)"},
                    "to": {"nodeId": "viewer", "key": "structures", "type": "Batch Structure"},
                }
            ],
        }
    )

    assert [error.code for error in validate_workflow(graph)] == ["DISCONNECTED_REQUIRED_PORT", "DISCONNECTED_REQUIRED_PORT"]


def test_run_validation_rejects_missing_input_uploads() -> None:
    request = RunCreateRequest.model_validate(
        {
            "workflow": {
                "nodes": [
                    {"id": "ligand", "type": "LigandInput", "outputs": {"ligand": {"type": "Ligand"}}},
                    {"id": "protein", "type": "ProteinInput", "outputs": {"batchProtein": {"type": "Batch Protein"}}},
                    {"id": "sequence", "type": "SequenceInput", "outputs": {"batchSequence": {"type": "Batch Sequence"}}},
                ],
                "connections": [],
            }
        }
    )

    errors = _validate_run_uploads(request)

    assert {error.code for error in errors} == {"MISSING_LIGAND_FILE", "MISSING_PROTEIN_FILE", "MISSING_FASTA_FILE"}


def test_run_validation_rejects_wrong_input_upload_type() -> None:
    request = RunCreateRequest.model_validate(
        {
            "workflow": {
                "nodes": [
                    {"id": "protein", "type": "ProteinInput", "outputs": {"batchProtein": {"type": "Batch Protein"}}},
                ],
                "connections": [],
            },
            "uploads": {"protein": [{"name": "sequence.fasta", "type": "fasta", "content": ">x\nACD\n"}]},
        }
    )

    errors = _validate_run_uploads(request)

    assert [error.code for error in errors] == ["INVALID_PROTEIN_FILE"]


def test_run_validation_matches_embedded_upload_by_filename_when_node_id_key_differs() -> None:
    request = RunCreateRequest.model_validate(
        {
            "document": {
                "fileType": "FoundryUIWorkflow",
                "workflow": {
                    "nodes": [
                        {
                            "id": "ligand",
                            "type": "LigandInput",
                            "options": {"file": "ligand.pdb"},
                            "outputs": {"ligand": {"type": "Ligand"}},
                        }
                    ],
                    "connections": [],
                },
                "uploads": {"baklava-node-id": [{"name": "ligand.pdb", "type": "pdb", "content": VALID_LIGAND_PDB}]},
            }
        }
    )

    assert _validate_run_uploads(request) == []
