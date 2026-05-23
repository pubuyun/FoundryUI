import gzip
from io import StringIO

from Bio.PDB import MMCIFIO, PDBParser

from backend.foundry_tools.common import collect_files
from backend.foundry_tools.mpnn import build_mpnn_command
from backend.foundry_tools.rfd3 import _standardize_rfd3_structures


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
