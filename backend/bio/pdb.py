from __future__ import annotations

from io import StringIO

from Bio.PDB import PDBParser


def validate_pdb(content: str) -> None:
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("uploaded", StringIO(content))
    atoms = list(structure.get_atoms())
    if not atoms:
        raise ValueError("PDB contains no atoms.")


def first_residue_name(content: str, default: str = "LIG") -> str:
    for line in content.splitlines():
        if line.startswith(("ATOM", "HETATM")) and len(line) >= 20:
            residue_name = line[17:20].strip()
            if residue_name:
                return residue_name
    return default


def rename_residue(content: str, residue_name: str) -> str:
    if len(residue_name) > 3:
        raise ValueError("PDB residue names must be three characters or fewer.")
    replacement = f"{residue_name:>3}"
    lines: list[str] = []
    for line in content.splitlines():
        if line.startswith(("ATOM", "HETATM")):
            line = f"{line[:17]}{replacement}{line[20:]}"
        lines.append(line)
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")


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
