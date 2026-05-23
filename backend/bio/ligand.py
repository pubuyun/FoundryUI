from __future__ import annotations

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


def ligand_has_chirality_targets(ligand_pdb: str, targets: list[tuple[str, str]]) -> bool:
    """Check selected PDB atom names against expected RDKit CIP labels."""
    if not targets:
        return True
    mol = _mol_from_pdb(ligand_pdb)
    if mol is None:
        return False
    chirality = _chirality_by_atom_name(mol)
    return all(chirality.get(atom_name) == expected for atom_name, expected in targets)


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


def _chirality_by_atom_name(mol) -> dict[str, str]:
    if Chem is None:
        raise ValueError("RDKit is required to compare ligand chirality.")
    try:
        if rdCIPLabeler is not None:
            rdCIPLabeler.AssignCIPLabels(mol)
        else:
            Chem.AssignStereochemistry(mol, force=True, cleanIt=True)
    except Exception:
        Chem.AssignStereochemistry(mol, force=True, cleanIt=True)
    labels: dict[str, str] = {}
    for atom in mol.GetAtoms():
        info = atom.GetPDBResidueInfo()
        if info is None:
            continue
        atom_name = info.GetName().strip()
        if atom_name and atom.HasProp("_CIPCode"):
            labels[atom_name] = atom.GetProp("_CIPCode")
    return labels
