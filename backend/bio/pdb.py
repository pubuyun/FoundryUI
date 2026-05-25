from __future__ import annotations

from io import StringIO

from Bio.PDB import PDBParser
from Bio.PDB.Polypeptide import protein_letters_3to1


STANDARD_RESIDUES = set(protein_letters_3to1)


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


def residue_selector_id(line: str) -> str:
    padded = line.ljust(80)
    resname = padded[17:20].strip()
    chain = padded[21].strip()
    resseq = padded[22:26].strip()
    if line.startswith("HETATM") or resname not in STANDARD_RESIDUES:
        return resname or f"{chain}{resseq}"
    return f"{chain}{resseq}"


def list_chain_ids(content: str) -> list[str]:
    chains: list[str] = []
    for line in content.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        chain = line[21].strip() if len(line) > 21 else ""
        if chain and chain not in chains:
            chains.append(chain)
    return chains


def filter_pdb_chains(content: str, chain_ids: list[str]) -> str:
    selected = set(chain_ids)
    lines = []
    for line in content.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        chain = line[21].strip() if len(line) > 21 else ""
        if chain in selected:
            lines.append(line)
    return "\n".join(lines + ["END", ""])


def filter_pdb_residues(content: str, residues: list[str]) -> str:
    selected = set(residues)
    lines = []
    for line in content.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        if residue_selector_id(line) in selected:
            lines.append(line)
    return "\n".join(lines + ["END", ""])


def rechain_pdb(content: str, chain_id: str, start_serial: int = 1) -> tuple[str, int]:
    lines: list[str] = []
    serial = start_serial
    for line in content.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        padded = line.ljust(80)
        lines.append(f"{padded[:6]}{serial:5d}{padded[11:21]}{chain_id[:1] or 'A'}{padded[22:]}")
        serial += 1
    return "\n".join(lines), serial


def merge_pdb_structures(contents: list[str]) -> str:
    chain_ids = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    merged: list[str] = []
    serial = 1
    for index, content in enumerate(contents):
        chain_id = chain_ids[index % len(chain_ids)]
        rechained, serial = rechain_pdb(content, chain_id, serial)
        if rechained:
            merged.extend(rechained.splitlines())
    return "\n".join([*merged, "END", ""])
