from __future__ import annotations

from collections import defaultdict

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from rdkit.Chem import rdCIPLabeler
except ImportError:  # pragma: no cover - exercised only when RDKit is unavailable
    Chem = None
    AllChem = None
    rdCIPLabeler = None


def smiles_to_pdb(smiles: str) -> str:
    if Chem is None or AllChem is None:
        raise ValueError("RDKit is required to convert SMILES to PDB.")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("SMILES is not parseable by RDKit.")
    mol = Chem.AddHs(mol)
    embed_status = AllChem.EmbedMolecule(mol, randomSeed=42)
    if embed_status != 0:
        raise ValueError("RDKit could not generate 3D coordinates from SMILES.")
    AllChem.UFFOptimizeMolecule(mol, maxIters=200)
    return Chem.MolToPDBBlock(mol)


def pdb_to_smiles(content: str) -> str:
    if Chem is None:
        raise ValueError("RDKit is required to convert ligand PDB to SMILES.")
    mol = Chem.MolFromPDBBlock(content, sanitize=True, removeHs=False)
    if mol is None:
        mol = Chem.MolFromPDBBlock(content, sanitize=False, removeHs=False)
    if mol is None:
        raise ValueError("Ligand PDB is not parseable by RDKit.")
    try:
        Chem.SanitizeMol(mol)
    except Exception:
        pass
    mol = Chem.RemoveHs(mol, sanitize=False)
    smiles = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    if not smiles:
        raise ValueError("RDKit could not generate SMILES from ligand PDB.")
    return smiles


def standardize_ligand_pdb(content: str, residue_name: str | None = None) -> tuple[str, str]:
    """Normalize ligand PDB records and return standardized PDB plus canonical isomeric SMILES."""
    mol = _mol_from_pdb(content)
    atom_lines = [line for line in content.splitlines() if line.startswith(("ATOM", "HETATM"))]
    if not atom_lines:
        raise ValueError("Ligand PDB contains no atom records.")
    if mol is None:
        raise ValueError("Ligand PDB is not parseable by RDKit.")
    atom_names = _standard_atom_names(mol, atom_lines)
    standardized = [_standardize_atom_line(line, index, atom_names[index - 1], residue_name) for index, line in enumerate(atom_lines, start=1)]
    return "\n".join([*standardized, "END", ""]), pdb_to_smiles("\n".join([*standardized, "END", ""]))


def ligand_matches_smiles_chirality(ligand_pdb: str, reference_smiles: str) -> bool:
    if not reference_smiles.strip():
        return True
    if Chem is None or AllChem is None:
        raise ValueError("RDKit is required to compare ligand chirality.")
    reference = Chem.MolFromSmiles(reference_smiles)
    if reference is None:
        raise ValueError("FilterChirality SMILES option is not parseable by RDKit.")
    reference = Chem.RemoveHs(reference)
    ligand = _mol_from_pdb(ligand_pdb)
    if ligand is None:
        return False
    ligand = Chem.RemoveHs(ligand, sanitize=False)
    try:
        Chem.SanitizeMol(ligand)
    except Exception:
        pass
    if ligand.GetNumAtoms() != reference.GetNumAtoms():
        return False
    try:
        ligand = AllChem.AssignBondOrdersFromTemplate(reference, ligand)
    except Exception:
        return False
    match = ligand.GetSubstructMatch(reference, useChirality=False)
    if not match or len(match) != reference.GetNumAtoms():
        return False
    _assign_smiles_stereochemistry(reference)
    _assign_3d_stereochemistry(ligand)
    reference_chirality = dict(Chem.FindMolChiralCenters(reference, force=True, includeUnassigned=False, includeCIP=True))
    ligand_chirality = dict(Chem.FindMolChiralCenters(ligand, force=True, includeUnassigned=False, includeCIP=True))
    for reference_index, expected in reference_chirality.items():
        if ligand_chirality.get(match[reference_index]) != expected:
            return False
    return True


def _mol_from_pdb(content: str):
    if Chem is None:
        raise ValueError("RDKit is required to compare ligand structures.")
    mol = Chem.MolFromPDBBlock(content, sanitize=True, removeHs=False)
    if mol is None:
        mol = Chem.MolFromPDBBlock(content, sanitize=False, removeHs=False)
    if mol is None:
        return None
    try:
        Chem.SanitizeMol(mol)
    except Exception:
        pass
    return mol


def _assign_smiles_stereochemistry(mol) -> None:
    if Chem is None:
        raise ValueError("RDKit is required to assign ligand stereochemistry.")
    Chem.AssignStereochemistry(mol, force=True, cleanIt=True)
    try:
        if rdCIPLabeler is not None:
            rdCIPLabeler.AssignCIPLabels(mol)
    except Exception:
        Chem.AssignStereochemistry(mol, force=True, cleanIt=True)


def _assign_3d_stereochemistry(mol) -> None:
    if Chem is None:
        raise ValueError("RDKit is required to assign ligand stereochemistry.")
    Chem.AssignStereochemistryFrom3D(mol, replaceExistingTags=True)
    try:
        if rdCIPLabeler is not None:
            rdCIPLabeler.AssignCIPLabels(mol)
    except Exception:
        Chem.AssignStereochemistry(mol, force=True, cleanIt=True)


def _standard_atom_names(mol, atom_lines: list[str]) -> list[str]:
    atom_count = len(atom_lines)
    if Chem is None or mol.GetNumAtoms() != atom_count:
        return _standard_atom_names_by_elements([_line_element_fallback(line) for line in atom_lines])
    ranks = list(Chem.CanonicalRankAtoms(mol, breakTies=True))
    counters: dict[str, int] = defaultdict(int)
    names_by_index = [""] * atom_count
    for atom_index in sorted(range(atom_count), key=lambda index: (ranks[index], index)):
        symbol = mol.GetAtomWithIdx(atom_index).GetSymbol().upper()
        counters[symbol] += 1
        names_by_index[atom_index] = f"{symbol}{counters[symbol]}"
    return names_by_index


def _standard_atom_names_by_elements(elements: list[str]) -> list[str]:
    counters: dict[str, int] = defaultdict(int)
    names = []
    for element in elements:
        counters[element] += 1
        names.append(f"{element}{counters[element]}")
    return names


def _standardize_atom_line(line: str, serial: int, atom_name: str, residue_name: str | None) -> str:
    padded = f"{line:<80}"[:80]
    element = _line_element(padded, atom_name)
    res_name = (residue_name or padded[17:20].strip() or "LIG")[:3]
    chain = padded[21].strip() or "L"
    residue_number = padded[22:26] if padded[22:26].strip() else "   1"
    insertion_code = padded[26] if len(padded) > 26 else " "
    coords = padded[30:54]
    try:
        float(coords[0:8])
        float(coords[8:16])
        float(coords[16:24])
    except ValueError:
        coords = f"{0.0:8.3f}{0.0:8.3f}{0.0:8.3f}"
    try:
        b_factor = float(padded[60:66])
    except ValueError:
        b_factor = 0.0
    charge = padded[78:80] if len(padded) >= 80 else "  "
    return (
        f"HETATM{serial:5d} {_format_atom_name(atom_name, element)} "
        f"{res_name:>3} {chain:1s}{residue_number:>4s}{insertion_code:1s}   "
        f"{coords}{1.00:6.2f}{b_factor:6.2f}          {element:>2s}{charge:>2s}"
    )


def _format_atom_name(atom_name: str, element: str) -> str:
    name = atom_name[:4]
    if len(element) == 1 and len(name) < 4:
        return f" {name:<3s}"
    return f"{name:<4s}"


def _line_element(line: str, atom_name: str) -> str:
    element = line[76:78].strip() if len(line) >= 78 else ""
    if element:
        return element.upper()
    letters = "".join(char for char in atom_name if char.isalpha())
    return (letters[:2] if len(letters) > 1 and letters[1].islower() else letters[:1] or "C").upper()


def _line_element_fallback(line: str) -> str:
    if not line:
        return "C"
    return _line_element(line, line[12:16].strip() or "C")
