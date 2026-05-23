import gzip
from io import StringIO

from Bio.PDB import MMCIFIO, PDBParser

from backend.bio.ligand import pdb_to_smiles, smiles_to_pdb
from backend.foundry_tools.common import collect_files
from backend.foundry_tools.mpnn import build_mpnn_command
from backend.foundry_tools.rf3 import build_rf3_jobs, collect_rf3_results
from backend.foundry_tools.rfd3 import _standardize_rfd3_structures
from backend.nodes.common import payload_from_artifacts
from backend.nodes.filters import _score_value
from backend.schemas.artifacts import ArtifactMetadata


PDB = """ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 40.00           N
ATOM      2  CA  GLY A   1       1.000   0.000   0.000  1.00 40.00           C
END
"""


def test_collect_files_matches_compound_suffix(tmp_path):
    cif_gz = tmp_path / "model.cif.gz"
    pdb = tmp_path / "model.pdb"
    cif_gz.write_text("compressed placeholder")
    pdb.write_text(PDB)

    assert collect_files(tmp_path, (".cif.gz",)) == [cif_gz]
    assert collect_files(tmp_path, (".pdb",)) == [pdb]


def test_rfd3_cif_gz_outputs_are_converted_to_pdb(tmp_path):
    out_dir = tmp_path / "rfd3_outputs"
    out_dir.mkdir()
    structure = PDBParser(QUIET=True).get_structure("model", StringIO(PDB))
    cif_path = tmp_path / "model.cif"
    writer = MMCIFIO()
    writer.set_structure(structure)
    writer.save(str(cif_path))
    cif_gz_path = out_dir / "model.cif.gz"
    with gzip.open(cif_gz_path, "wt") as handle:
        handle.write(cif_path.read_text())

    paths = _standardize_rfd3_structures(out_dir, tmp_path / "pdb_outputs")

    assert len(paths) == 1
    assert paths[0].suffix == ".pdb"
    assert "ATOM" in paths[0].read_text()


def test_mpnn_command_uses_foundry_inference_script(tmp_path):
    command = build_mpnn_command(
        inference_script=tmp_path / "inference.py",
        checkpoint_path=tmp_path / "ligand.pt",
        out_dir=tmp_path / "outputs",
        structure_path=tmp_path / "input.pdb",
        model_type="ligand_mpnn",
        residue_role="redesigned_residues",
        residues=["A1", "A2"],
        number_of_batches=5,
        batch_size=3,
        seed=111,
        temperature=0.05,
        bias_aa="W:3.0,P:3.0,A:-3.0",
        omit_aa="CDF",
    )

    assert str(tmp_path / "inference.py") in command
    assert command[command.index("--model_type") + 1] == "ligand_mpnn"
    assert command[command.index("--checkpoint_path") + 1] == str(tmp_path / "ligand.pt")
    assert command[command.index("--structure_path") + 1] == str(tmp_path / "input.pdb")
    assert command[command.index("--out_directory") + 1] == str(tmp_path / "outputs")
    assert command[command.index("--designed_residues") + 1] == "A1,A2"
    assert command[command.index("--bias") + 1] == '{"TRP": 3.0, "PRO": 3.0, "ALA": -3.0}'
    assert command[command.index("--omit") + 1] == '["CYS", "ASP", "PHE"]'


def test_rf3_jobs_use_component_json_with_ligand_smiles():
    jobs = build_rf3_jobs(
        [{"id": "design 1", "sequence": "ACDE"}, {"id": "empty", "sequence": ""}],
        "CCO",
    )

    assert jobs == [
        {
            "name": "design_1",
            "components": [
                {"seq": "ACDE", "chain_id": "A"},
                {"smiles": "CCO"},
            ],
        }
    ]


def test_ligand_pdb_can_be_converted_to_smiles_for_rf3():
    pdb = smiles_to_pdb("CCO")

    assert pdb_to_smiles(pdb) == "CCO"


def test_rf3_collects_only_top_level_model_and_scores(tmp_path):
    out_dir = tmp_path / "rf3_outputs"
    result_dir = out_dir / "design_1"
    result_dir.mkdir(parents=True)
    seed_dir = result_dir / "seed-42_sample-0"
    seed_dir.mkdir()
    structure = PDBParser(QUIET=True).get_structure("model", StringIO(PDB))
    writer = MMCIFIO()
    writer.set_structure(structure)
    writer.save(str(result_dir / "design_1_model.cif"))
    writer.save(str(seed_dir / "ignored_model.cif"))
    (result_dir / "design_1_summary_confidences.json").write_text(
        '{"ranking_score": 0.9, "ptm": 0.8, "iptm": 0.7, "overall_plddt": 0.65, "has_clash": false, "length": 2}'
    )

    paths, scores = collect_rf3_results(out_dir, tmp_path / "rf3_pdb_outputs")

    assert len(paths) == 1
    assert paths[0].suffix == ".pdb"
    assert "ATOM" in paths[0].read_text()
    assert scores == [
        {
            "design_id": "design_1",
            "length": 2,
            "ranking_score": 0.9,
            "pTM": 0.8,
            "ipTM": 0.7,
            "pLDDT": 65.0,
            "interface_PAE": None,
            "has_clash": False,
        }
    ]


def test_score_value_handles_missing_optional_metrics():
    assert _score_value({"interface_PAE": None}, "interface_PAE", float("inf")) == float("inf")
    assert _score_value({"ranking_score": "0.92"}, "ranking_score", float("-inf")) == 0.92


def test_score_payload_item_count_tracks_rows_not_artifact_files():
    artifacts = [
        ArtifactMetadata(artifact_id="json", run_id="run", payload_type="Score", path="scores.json", item_count=10),
        ArtifactMetadata(artifact_id="csv", run_id="run", payload_type="Score", path="scores.csv", item_count=10),
    ]

    payload = payload_from_artifacts("Score", artifacts, data=[{}] * 10, item_count=10)

    assert payload.item_count == 10
    assert len(payload.artifact_ids) == 2
