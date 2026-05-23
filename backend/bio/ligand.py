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


def sdf_to_smiles(content: str) -> str:
    if Chem is None:
        raise ValueError("RDKit is required to convert SDF to SMILES.")
    tmp = Path("/tmp/foundryui-upload-smiles.sdf")
    tmp.write_text(content)
    supplier = Chem.SDMolSupplier(str(tmp), sanitize=True, removeHs=False)
    mol = next((candidate for candidate in supplier if candidate is not None), None)
    tmp.unlink(missing_ok=True)
    if mol is None:
        raise ValueError("SDF contains no valid molecules.")
    mol = Chem.RemoveHs(mol, sanitize=False)
    smiles = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    if not smiles:
        raise ValueError("RDKit could not generate SMILES from SDF.")
    return smiles


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
