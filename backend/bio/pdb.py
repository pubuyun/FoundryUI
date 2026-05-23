from __future__ import annotations

from io import StringIO

from Bio.PDB import PDBParser


def validate_pdb(content: str) -> None:
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("uploaded", StringIO(content))
    atoms = list(structure.get_atoms())
    if not atoms:
        raise ValueError("PDB contains no atoms.")


def split_pdb_complex(content: str) -> tuple[str, str]:
    protein_lines: list[str] = []
    ligand_lines: list[str] = []
    for line in content.splitlines():
        if line.startswith("ATOM"):
            protein_lines.append(line)
        elif line.startswith("HETATM"):
            ligand_lines.append(line)
    return "\n".join(protein_lines + ["END\n"]), "\n".join(ligand_lines + ["END\n"])


def merge_pdb(protein: str, ligand: str) -> str:
    protein_body = [line for line in protein.splitlines() if not line.startswith("END")]
    ligand_body = [line for line in ligand.splitlines() if not line.startswith("END")]
    return "\n".join([*protein_body, *ligand_body, "END", ""])
