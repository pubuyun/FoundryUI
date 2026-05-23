from __future__ import annotations

from Bio.PDB.Polypeptide import protein_letters_3to1


def pdb_to_sequence(content: str) -> str:
    residues: list[str] = []
    seen: set[tuple[str, str]] = set()
    for line in content.splitlines():
        if not line.startswith("ATOM"):
            continue
        chain = line[21:22].strip()
        resseq = line[22:26].strip()
        resname = line[17:20].strip().upper()
        key = (chain, resseq)
        if key in seen:
            continue
        seen.add(key)
        residues.append(protein_letters_3to1.get(resname, "X"))
    return "".join(residues)
