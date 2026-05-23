from __future__ import annotations

from backend.nodes.filters import filter_by_ligand, filter_by_score
from backend.nodes.folding import rosetta_fold
from backend.nodes.generation import rfdiffusion_smbinder
from backend.nodes.inputs import ligand_input, protein_input, sequence_input
from backend.nodes.logic import binary_logic
from backend.nodes.mpnn import ligand_mpnn, protein_mpnn
from backend.nodes.save import save_ligands, save_proteins_with_scores, save_sequences
from backend.nodes.selectors import atom_selector, residue_selector
from backend.nodes.utils import merge, protein_to_seq, split
from backend.nodes.viewers import pdb_viewer, sequence_viewer
from backend.schemas.payloads import TypedPayload
from backend.schemas.workflow import WorkflowNode
from backend.nodes.common import ExecutionContext


async def primitive_value(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    return {"value": TypedPayload(type_name="Any", item_count=1, data=node.options.get("value"))}


async def note(ctx: ExecutionContext, node: WorkflowNode, inputs: dict[str, TypedPayload]) -> dict[str, TypedPayload]:
    return {}


HANDLERS = {
    "MDNote": note,
    "LigandInput": ligand_input,
    "ProteinInput": protein_input,
    "SequenceInput": sequence_input,
    "AtomSelector": atom_selector,
    "ResidueSelector": residue_selector,
    "RFDiffusionSMbinder": rfdiffusion_smbinder,
    "LigandMPNN": ligand_mpnn,
    "ProteinMPNN": protein_mpnn,
    "RosettaFold": rosetta_fold,
    "RosettaFold3": rosetta_fold,
    "FilterByScore": filter_by_score,
    "FilterByLigand": filter_by_ligand,
    "BinaryLogic": binary_logic,
    "Protein2Seq": protein_to_seq,
    "Merge": merge,
    "Split": split,
    "PDBViewer": pdb_viewer,
    "SequenceViewer": sequence_viewer,
    "SaveProteinsWithScores": save_proteins_with_scores,
    "SaveSequences": save_sequences,
    "SaveLigands": save_ligands,
    "StringPrimitive": primitive_value,
    "IntPrimitive": primitive_value,
    "FloatPrimitive": primitive_value,
}
