from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PortSpec:
    key: str
    type_name: str
    optional: bool = False


@dataclass(frozen=True)
class OptionSpec:
    key: str
    kind: str
    default: Any = None
    required: bool = False
    choices: tuple[Any, ...] = ()
    min_value: float | None = None
    max_value: float | None = None


@dataclass(frozen=True)
class NodeSpec:
    type_name: str
    inputs: dict[str, PortSpec] = field(default_factory=dict)
    options: dict[str, OptionSpec] = field(default_factory=dict)
    outputs: dict[str, PortSpec] = field(default_factory=dict)
    terminal: bool = False


def _ports(items: list[PortSpec]) -> dict[str, PortSpec]:
    return {item.key: item for item in items}


def _options(items: list[OptionSpec]) -> dict[str, OptionSpec]:
    return {item.key: item for item in items}


NODE_CATALOG: dict[str, NodeSpec] = {
    "MDNote": NodeSpec(
        "MDNote",
        options=_options([OptionSpec("note", "textarea", "")]),
        terminal=True,
    ),
    "ResidueSelector": NodeSpec(
        "ResidueSelector",
        inputs=_ports([PortSpec("protein", "Protein", optional=True)]),
        options=_options([OptionSpec("residues", "text", ""), OptionSpec("viewer", "viewer", "Open")]),
        outputs=_ports([PortSpec("residues", "List of Residues")]),
    ),
    "AtomSelector": NodeSpec(
        "AtomSelector",
        inputs=_ports([PortSpec("ligand", "Ligand", optional=True)]),
        options=_options([OptionSpec("atoms", "text", ""), OptionSpec("viewer", "viewer", "Open")]),
        outputs=_ports([PortSpec("atoms", "List of Atoms")]),
    ),
    "LigandInput": NodeSpec(
        "LigandInput",
        options=_options(
            [
                OptionSpec("file", "file", ""),
                OptionSpec("viewer", "viewer", "Open"),
            ]
        ),
        outputs=_ports([PortSpec("ligand", "Ligand")]),
    ),
    "ProteinInput": NodeSpec(
        "ProteinInput",
        options=_options([OptionSpec("file", "file", ""), OptionSpec("viewer", "viewer", "Open")]),
        outputs=_ports([PortSpec("batchProtein", "Batch Protein")]),
    ),
    "SequenceInput": NodeSpec(
        "SequenceInput",
        options=_options([OptionSpec("file", "file", "")]),
        outputs=_ports([PortSpec("batchSequence", "Batch Sequence")]),
    ),
    "RFDiffusionSMbinder": NodeSpec(
        "RFDiffusionSMbinder",
        inputs=_ports(
            [
                PortSpec("ligand", "Ligand"),
                PortSpec("selectFixedAtoms", "List of Atoms", optional=True),
                PortSpec("selectBuried", "List of Atoms", optional=True),
                PortSpec("selectExposed", "List of Atoms", optional=True),
            ]
        ),
        options=_options(
            [
                OptionSpec("length", "text", "50-200", required=True),
                OptionSpec("nBatches", "int", 1, min_value=1),
                OptionSpec("diffusionBatchSize", "int", 5, min_value=1),
            ]
        ),
        outputs=_ports([PortSpec("complexes", "Batch Protein (With Ligand)")]),
    ),
    "LigandMPNN": NodeSpec(
        "LigandMPNN",
        inputs=_ports(
            [
                PortSpec("complexes", "Batch Protein (With Ligand)"),
                PortSpec("residues", "List of Residues", optional=True),
            ]
        ),
        options=_options(
            [
                OptionSpec("residueRole", "select", "fixed_residues", choices=("fixed_residues", "redesigned_residues")),
                OptionSpec("numberOfBatches", "int", required=True, min_value=1),
                OptionSpec("batchSize", "int", required=True, min_value=1),
                OptionSpec("seed", "int", 42, min_value=0),
                OptionSpec("temperature", "float", 0.05, min_value=0, max_value=5),
                OptionSpec("biasAA", "text", ""),
                OptionSpec("omitAA", "text", ""),
            ]
        ),
        outputs=_ports([PortSpec("sequences", "Batch Sequence")]),
    ),
    "ProteinMPNN": NodeSpec(
        "ProteinMPNN",
        inputs=_ports(
            [
                PortSpec("batchProtein", "Batch Protein"),
                PortSpec("residues", "List of Residues", optional=True),
            ]
        ),
        options=_options(
            [
                OptionSpec("residueRole", "select", "fixed_residues", choices=("fixed_residues", "redesigned_residues")),
                OptionSpec("numberOfBatches", "int", required=True, min_value=1),
                OptionSpec("batchSize", "int", required=True, min_value=1),
                OptionSpec("seed", "int", 42, min_value=0),
                OptionSpec("temperature", "float", 0.05, min_value=0, max_value=5),
                OptionSpec("biasAA", "text", ""),
                OptionSpec("omitAA", "text", ""),
            ]
        ),
        outputs=_ports([PortSpec("sequences", "Batch Sequence")]),
    ),
    "RosettaFold": NodeSpec(
        "RosettaFold",
        inputs=_ports([PortSpec("sequences", "Batch Sequence"), PortSpec("ligand", "Ligand", optional=True)]),
        options=_options(
            [
                OptionSpec("earlyStoppingPlddtThreshold", "float", 0.5, min_value=0, max_value=1),
                OptionSpec("diffusionBatchSize", "int", 5, min_value=1),
                OptionSpec("numSteps", "int", 50, min_value=1),
                OptionSpec("seed", "int", 42, min_value=0),
            ]
        ),
        outputs=_ports([PortSpec("structures", "Batch Protein (With Ligand)"), PortSpec("score", "Score")]),
    ),
    "RosettaFold3": NodeSpec(
        "RosettaFold3",
        inputs=_ports([PortSpec("sequences", "Batch Sequence"), PortSpec("ligand", "Ligand", optional=True)]),
        options=_options(
            [
                OptionSpec("earlyStoppingPlddtThreshold", "float", 0.5, min_value=0, max_value=1),
                OptionSpec("diffusionBatchSize", "int", 5, min_value=1),
                OptionSpec("numSteps", "int", 50, min_value=1),
                OptionSpec("seed", "int", 42, min_value=0),
            ]
        ),
        outputs=_ports([PortSpec("structures", "Batch Protein (With Ligand)"), PortSpec("score", "Score")]),
    ),
    "FilterByScore": NodeSpec(
        "FilterByScore",
        inputs=_ports([PortSpec("structures", "Batch Protein (With Ligand)"), PortSpec("score", "Score")]),
        options=_options(
            [
                OptionSpec("metric", "select", "pLDDT", choices=("pLDDT", "length", "pTM", "interface_PAE", "ipTM", "ranking_score")),
                OptionSpec("mode", "select", "Is largest top", choices=("Is largest top", "Is smallest top", "Higher than", "Lower than")),
                OptionSpec("threshold", "float", 10),
            ]
        ),
        outputs=_ports([PortSpec("structures", "Batch Protein (With Ligand)"), PortSpec("score", "Score")]),
    ),
    "FilterChirality": NodeSpec(
        "FilterChirality",
        inputs=_ports(
            [
                PortSpec("complexes", "Batch Protein (With Ligand)"),
                PortSpec("score", "Score", optional=True),
            ]
        ),
        options=_options([OptionSpec("targets", "textarea", "")]),
        outputs=_ports([PortSpec("complexes", "Batch Protein (With Ligand)"), PortSpec("score", "Score")]),
    ),
    "BinaryLogic": NodeSpec(
        "BinaryLogic",
        inputs=_ports(
            [
                PortSpec("structures1", "Batch Protein (With Ligand)"),
                PortSpec("score1", "Score", optional=True),
                PortSpec("structures2", "Batch Protein (With Ligand)"),
                PortSpec("score2", "Score", optional=True),
            ]
        ),
        options=_options([OptionSpec("operation", "select", "OR", choices=("OR", "AND", "NOR", "NAND", "XOR"))]),
        outputs=_ports([PortSpec("structures", "Batch Protein (With Ligand)"), PortSpec("score", "Score")]),
    ),
    "Protein2Seq": NodeSpec(
        "Protein2Seq",
        inputs=_ports([PortSpec("batchProtein", "Batch Protein")]),
        outputs=_ports([PortSpec("sequences", "Batch Sequence")]),
    ),
    "Merge": NodeSpec(
        "Merge",
        inputs=_ports([PortSpec("ligand", "Ligand"), PortSpec("batchProtein", "Batch Protein")]),
        outputs=_ports([PortSpec("complexes", "Batch Protein (With Ligand)")]),
    ),
    "Split": NodeSpec(
        "Split",
        inputs=_ports([PortSpec("complexes", "Batch Protein (With Ligand)")]),
        outputs=_ports([PortSpec("batchLigand", "Batch Ligand"), PortSpec("batchProtein", "Batch Protein")]),
    ),
    "PDBViewer": NodeSpec(
        "PDBViewer",
        inputs=_ports([PortSpec("structures", "Batch Protein (With Ligand)")]),
        options=_options([OptionSpec("viewer", "viewer", "Open")]),
        terminal=True,
    ),
    "SequenceViewer": NodeSpec(
        "SequenceViewer",
        inputs=_ports([PortSpec("sequences", "Batch Sequence")]),
        options=_options([OptionSpec("file", "text", "")]),
        terminal=True,
    ),
    "SaveProteinsWithScores": NodeSpec(
        "SaveProteinsWithScores",
        inputs=_ports([PortSpec("structures", "Batch Protein (With Ligand)"), PortSpec("score", "Score")]),
        options=_options([OptionSpec("folder", "text", "outputs/proteins")]),
        terminal=True,
    ),
    "SaveProteins": NodeSpec(
        "SaveProteins",
        inputs=_ports([PortSpec("structures", "Batch Protein (With Ligand)")]),
        options=_options([OptionSpec("folder", "text", "outputs/proteins")]),
        terminal=True,
    ),
    "SaveSequences": NodeSpec(
        "SaveSequences",
        inputs=_ports([PortSpec("sequences", "Batch Sequence")]),
        options=_options([OptionSpec("folder", "text", "outputs/sequences")]),
        terminal=True,
    ),
    "SaveLigands": NodeSpec(
        "SaveLigands",
        inputs=_ports([PortSpec("ligand", "Ligand")]),
        options=_options([OptionSpec("folder", "text", "outputs/ligands")]),
        terminal=True,
    ),
    "StringPrimitive": NodeSpec("StringPrimitive", options=_options([OptionSpec("value", "text", "")]), outputs=_ports([PortSpec("value", "Any")])),
    "IntPrimitive": NodeSpec("IntPrimitive", options=_options([OptionSpec("value", "int", 0)]), outputs=_ports([PortSpec("value", "Any")])),
    "FloatPrimitive": NodeSpec("FloatPrimitive", options=_options([OptionSpec("value", "float", 0.0)]), outputs=_ports([PortSpec("value", "Any")])),
}


def spec_for(node_type: str) -> NodeSpec | None:
    if node_type == "RosettaFold3":
        return NODE_CATALOG["RosettaFold3"]
    return NODE_CATALOG.get(node_type)
