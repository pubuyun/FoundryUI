from __future__ import annotations

from pathlib import Path

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
except ImportError:  # pragma: no cover - exercised only when RDKit is unavailable
    Chem = None
    AllChem = None


def validate_sdf(content: str) -> None:
    if Chem is None:
        raise ValueError("RDKit is required to parse SDF files.")
    supplier = Chem.ForwardSDMolSupplier(content.encode("utf-8"), sanitize=True, removeHs=False)
    mols = [mol for mol in supplier if mol is not None]
    if not mols:
        raise ValueError("SDF contains no valid molecules.")


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


def sdf_to_pdb(content: str) -> str:
    if Chem is None:
        raise ValueError("RDKit is required to convert SDF to PDB.")
    tmp = Path("/tmp/foundryui-upload.sdf")
    tmp.write_text(content)
    supplier = Chem.SDMolSupplier(str(tmp), sanitize=True, removeHs=False)
    mol = next((candidate for candidate in supplier if candidate is not None), None)
    tmp.unlink(missing_ok=True)
    if mol is None:
        raise ValueError("SDF contains no valid molecules.")
    return Chem.MolToPDBBlock(mol)
