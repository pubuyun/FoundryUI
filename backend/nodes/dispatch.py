from __future__ import annotations

from backend.nodes.filters import filter_atoms_chirality, filter_chirality, filter_by_score
from backend.nodes.folding import rosetta_fold
from backend.nodes.generation import rfdiffusion_enzyme, rfdiffusion_protein_binder, rfdiffusion_smbinder
from backend.nodes.inputs import ligand_input, protein_input, protein_with_ligand_input, sequence_input
from backend.nodes.logic import binary_logic
from backend.nodes.mpnn import ligand_mpnn, protein_mpnn
from backend.nodes.save import save_ligands, save_proteins, save_proteins_with_scores, save_sequences
from backend.nodes.selectors import atom_selector, protein_chain_selector, protein_atom_selector, residue_selector
from backend.nodes.utils import merge, protein_to_seq, split
from backend.nodes.common import ExecutionContext
from backend.nodes.viewers import pdb_viewer, sequence_viewer
from backend.nodes.scoring import calculate_ligand_rmsd, calculate_protein_rmsd
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode


async def note(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    return {}


HANDLERS = {
    "MDNote": note,
    "LigandInput": ligand_input,
    "ProteinInput": protein_input,
    "ProteinWithLigandInput": protein_with_ligand_input,
    "SequenceInput": sequence_input,
    "AtomSelector": atom_selector,
    "ResidueSelector": residue_selector,
    "ProteinAtomSelector": protein_atom_selector,
    "ResidueAtomSelector": protein_atom_selector,
    "ProteinChainSelector": protein_chain_selector,
    "ChainFilter": protein_chain_selector,
    "RFDiffusionSMbinder": rfdiffusion_smbinder,
    "RFDiffusionProteinBinder": rfdiffusion_protein_binder,
    "RFDiffusionEnzyme": rfdiffusion_enzyme,
    "LigandMPNN": ligand_mpnn,
    "ProteinMPNN": protein_mpnn,
    "RosettaFold": rosetta_fold,
    "RosettaFold3": rosetta_fold,
    "FilterByScore": filter_by_score,
    "CalculateProteinRMSD": calculate_protein_rmsd,
    "CalculateLigandRMSD": calculate_ligand_rmsd,
    "FilterChirality": filter_chirality,
    "FilterAtomsChirality": filter_atoms_chirality,
    "BinaryLogic": binary_logic,
    "Protein2Seq": protein_to_seq,
    "Merge": merge,
    "Split": split,
    "PDBViewer": pdb_viewer,
    "SequenceViewer": sequence_viewer,
    "SaveProteinsWithScores": save_proteins_with_scores,
    "SaveProteins": save_proteins,
    "SaveSequences": save_sequences,
    "SaveLigands": save_ligands,
}
