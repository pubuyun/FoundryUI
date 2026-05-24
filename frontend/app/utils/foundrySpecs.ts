export type PortType =
  | "Ligand"
  | "Protein"
  | "List of Residues"
  | "List of Atoms"
  | "Batch Protein"
  | "Batch Ligand"
  | "Batch Protein (With Ligand)"
  | "Batch Sequence"
  | "Score";

export type OptionKind = "text" | "textarea" | "int" | "float" | "bool" | "select" | "file" | "viewer";

export interface PortSpec {
  key: string;
  label: string;
  type: PortType;
  optional?: boolean;
}

export interface OptionSpec {
  key: string;
  label: string;
  kind: OptionKind;
  value: string | number | boolean;
  items?: string[];
  accept?: string;
  min?: number;
  max?: number;
  viewerMode?: "residue" | "atom" | "structure" | "batchStructure" | "sequence";
}

export interface FoundryNodeSpec {
  type: string;
  title: string;
  category: string;
  description: string;
  inputs?: PortSpec[];
  options?: OptionSpec[];
  outputs?: PortSpec[];
}

export const proteinExample = `ATOM      1  N   GLY A  58      -6.730  -1.637   0.000  1.00 40.00           N
ATOM      2  CA  GLY A  58      -5.454  -0.921   0.000  1.00 40.00           C
ATOM      3  C   GLY A  58      -4.284  -1.891   0.000  1.00 40.00           C
ATOM      4  O   GLY A  58      -4.404  -3.115   0.000  1.00 40.00           O
ATOM      5  N   SER A  59      -3.153  -1.333   0.000  1.00 40.00           N
ATOM      6  CA  SER A  59      -1.937  -2.128   0.000  1.00 40.00           C
ATOM      7  C   SER A  59      -0.711  -1.228   0.000  1.00 40.00           C
ATOM      8  O   SER A  59      -0.799   0.000   0.000  1.00 40.00           O
ATOM      9  CB  SER A  59      -1.780  -3.003   1.238  1.00 40.00           C
ATOM     10  OG  SER A  59      -2.932  -3.813   1.431  1.00 40.00           O
ATOM     11  N   LEU A 103       0.432  -1.847   0.000  1.00 40.00           N
ATOM     12  CA  LEU A 103       1.680  -1.092   0.000  1.00 40.00           C
ATOM     13  C   LEU A 103       2.903  -1.999   0.000  1.00 40.00           C
ATOM     14  O   LEU A 103       2.765  -3.217   0.000  1.00 40.00           O
HETATM   15  C1  LIG B   1       0.114   1.782   0.000  1.00 20.00           C
HETATM   16  C2  LIG B   1       1.454   1.208   0.000  1.00 20.00           C
HETATM   17  O2  LIG B   1       2.505   2.087   0.000  1.00 20.00           O
HETATM   18  N1  LIG B   1       1.556  -0.198   0.000  1.00 20.00           N
END`;

export const typeDetails: Array<{ name: PortType; detail: string }> = [
  { name: "Ligand", detail: "Single small-molecule PDB payload" },
  { name: "Protein", detail: "Single protein PDB payload" },
  { name: "List of Residues", detail: 'Residue ids such as "A58,A103"' },
  { name: "List of Atoms", detail: 'Ligand atom ids such as "C1,O2"' },
  { name: "Batch Protein", detail: "Protein model collection" },
  { name: "Batch Ligand", detail: "Ligand conformer collection" },
  { name: "Batch Protein (With Ligand)", detail: "Protein or protein-ligand complex collection" },
  { name: "Batch Sequence", detail: "Sequence collection from FASTA or design output" },
  { name: "Score", detail: "List of score dictionaries from folding/filtering" },
];

export const colorsByType: Record<PortType, string> = {
  Ligand: "#249a86",
  Protein: "#4678d4",
  "List of Residues": "#9062ce",
  "List of Atoms": "#e2559b",
  "Batch Protein": "#2368ad",
  "Batch Ligand": "#168b69",
  "Batch Protein (With Ligand)": "#c74b67",
  "Batch Sequence": "#7d8b23",
  Score: "#d28a19",
};

export const nodeSpecs: FoundryNodeSpec[] = [
  {
    type: "MDNote",
    title: "MD Note",
    category: "Note",
    description: "Free-form workflow note. No data ports.",
    options: [{ key: "note", label: "Text Field", kind: "textarea", value: "Design notes" }],
  },
  {
    type: "ResidueSelector",
    title: "Residue Selector",
    category: "Selector",
    description: 'Use a node-local 3D viewer or type residue ids such as "A103,A201".',
    inputs: [{ key: "protein", label: "Protein", type: "Protein", optional: true }],
    options: [
      { key: "residues", label: "Text Field", kind: "text", value: "A103,A201" },
      { key: "viewer", label: "3D Viewer residue selector", kind: "viewer", value: "Open", viewerMode: "residue" },
    ],
    outputs: [{ key: "residues", label: "List of Residues", type: "List of Residues" }],
  },
  {
    type: "AtomSelector",
    title: "Atom Selector",
    category: "Selector",
    description: 'Use a node-local 3D viewer or type atom ids such as "C1,C2".',
    inputs: [{ key: "ligand", label: "Ligand", type: "Ligand", optional: true }],
    options: [
      { key: "atoms", label: "Text Field", kind: "text", value: "C1,C2" },
      { key: "viewer", label: "3D Viewer atom selector", kind: "viewer", value: "Open", viewerMode: "atom" },
    ],
    outputs: [{ key: "atoms", label: "List of Atoms", type: "List of Atoms" }],
  },
  {
    type: "LigandInput",
    title: "Ligand Input",
    category: "Structure Inputs",
    description: "Manual ligand input from PDB upload.",
    options: [
      { key: "file", label: "Upload File", kind: "file", value: "", accept: ".pdb" },
      { key: "viewer", label: "3D Viewer", kind: "viewer", value: "Open", viewerMode: "structure" },
    ],
    outputs: [{ key: "ligand", label: "Ligand", type: "Ligand" }],
  },
  {
    type: "ProteinInput",
    title: "Protein Input",
    category: "Structure Inputs",
    description: "Manual batch protein input from PDB files.",
    options: [
      { key: "file", label: "Upload File", kind: "file", value: "", accept: ".pdb" },
      { key: "viewer", label: "File Selector + 3D Viewer", kind: "viewer", value: "Open", viewerMode: "batchStructure" },
    ],
    outputs: [{ key: "batchProtein", label: "Batch Protein", type: "Batch Protein" }],
  },
  {
    type: "SequenceInput",
    title: "Sequence Input",
    category: "Structure Inputs",
    description: "Manual batch sequence input from FASTA files.",
    options: [{ key: "file", label: "Upload File", kind: "file", value: "", accept: ".fasta,.fa" }],
    outputs: [{ key: "batchSequence", label: "Batch Sequence", type: "Batch Sequence" }],
  },
  {
    type: "RFDiffusionSMbinder",
    title: "RFDiffusion3 SM Binder",
    category: "Generation",
    description: "RFdiffusion3 small-molecule binder generation.",
    inputs: [
      { key: "ligand", label: "Ligand", type: "Ligand" },
      { key: "selectFixedAtoms", label: "select_fixed_atoms", type: "List of Atoms", optional: true },
      { key: "selectBuried", label: "select_buried", type: "List of Atoms", optional: true },
      { key: "selectExposed", label: "select_exposed", type: "List of Atoms", optional: true },
    ],
    options: [
      { key: "length", label: "length", kind: "text", value: "50-200" },
      { key: "nBatches", label: "n_batches", kind: "int", value: 1, min: 1 },
      { key: "diffusionBatchSize", label: "diffusion_batch_size", kind: "int", value: 5, min: 1 },
    ],
    outputs: [{ key: "complexes", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" }],
  },
  {
    type: "LigandMPNN",
    title: "Ligand MPNN",
    category: "MPNN",
    description: "Ligand-aware sequence design for protein-ligand complexes.",
    inputs: [
      { key: "complexes", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" },
      { key: "residues", label: "List of Residues: fixed/redesigned", type: "List of Residues", optional: true },
    ],
    options: [
      { key: "residueRole", label: "Residue input role", kind: "select", value: "fixed_residues", items: ["fixed_residues", "redesigned_residues"] },
      { key: "numberOfBatches", label: "number_of_batches", kind: "int", value: 4, min: 1 },
      { key: "batchSize", label: "batch_size", kind: "int", value: 8, min: 1 },
      { key: "seed", label: "seed", kind: "int", value: 42, min: 0 },
      { key: "temperature", label: "temperature", kind: "float", value: 0.05, min: 0, max: 5 },
      { key: "biasAA", label: "bias_AA", kind: "text", value: "" },
      { key: "omitAA", label: "omit_AA", kind: "text", value: "" },
    ],
    outputs: [{ key: "sequences", label: "Batch Sequence", type: "Batch Sequence" }],
  },
  {
    type: "ProteinMPNN",
    title: "Protein MPNN",
    category: "MPNN",
    description: "Sequence design for protein batches without ligand context.",
    inputs: [
      { key: "batchProtein", label: "Batch Protein", type: "Batch Protein" },
      { key: "residues", label: "List of Residues: fixed/redesigned", type: "List of Residues", optional: true },
    ],
    options: [
      { key: "residueRole", label: "Residue input role", kind: "select", value: "fixed_residues", items: ["fixed_residues", "redesigned_residues"] },
      { key: "numberOfBatches", label: "number_of_batches", kind: "int", value: 4, min: 1 },
      { key: "batchSize", label: "batch_size", kind: "int", value: 8, min: 1 },
      { key: "seed", label: "seed", kind: "int", value: 42, min: 0 },
      { key: "temperature", label: "temperature", kind: "float", value: 0.05, min: 0, max: 5 },
      { key: "biasAA", label: "bias_AA", kind: "text", value: "" },
      { key: "omitAA", label: "omit_AA", kind: "text", value: "" },
    ],
    outputs: [{ key: "sequences", label: "Batch Sequence", type: "Batch Sequence" }],
  },
  {
    type: "RosettaFold",
    title: "RosettaFold3",
    category: "Folding",
    description: "Fold batch sequences, optionally with ligand co-folding.",
    inputs: [
      { key: "sequences", label: "Batch Sequence", type: "Batch Sequence" },
      { key: "ligand", label: "Ligand", type: "Ligand", optional: true },
    ],
    options: [
      { key: "earlyStoppingPlddtThreshold", label: "early_stopping_plddt_threshold", kind: "float", value: 0.5, min: 0, max: 1 },
      { key: "diffusionBatchSize", label: "diffusion_batch_size", kind: "int", value: 5, min: 1 },
      { key: "numSteps", label: "num_steps", kind: "int", value: 50, min: 1 },
      { key: "seed", label: "seed", kind: "int", value: 42, min: 0 },
    ],
    outputs: [
      { key: "structures", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" },
      { key: "score", label: "Score", type: "Score" },
    ],
  },
  {
    type: "FilterByScore",
    title: "Filter By Score",
    category: "Filter",
    description: "Filter model batches by one score metric, preserving score ordering.",
    inputs: [
      { key: "structures", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" },
      { key: "score", label: "Score", type: "Score" },
    ],
    options: [
      { key: "metric", label: "Specific Score", kind: "select", value: "pLDDT", items: ["pLDDT", "length", "pTM", "interface_PAE", "ipTM", "ranking_score"] },
      { key: "mode", label: "Filter Mode", kind: "select", value: "Is largest top", items: ["Is largest top", "Is smallest top", "Higher than", "Lower than"] },
      { key: "threshold", label: "top / threshold", kind: "float", value: 10 },
    ],
    outputs: [
      { key: "structures", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" },
      { key: "score", label: "Score", type: "Score" },
    ],
  },
  {
    type: "FilterChirality",
    title: "Filter Chirality",
    category: "Filter",
    description: "Keep complexes whose ligand atoms match selected chirality targets.",
    inputs: [
      { key: "complexes", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" },
      { key: "score", label: "Score", type: "Score", optional: true },
    ],
    options: [{ key: "targets", label: "Atom chirality pairs", kind: "textarea", value: "C0:S" }],
    outputs: [
      { key: "complexes", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" },
      { key: "score", label: "Score", type: "Score" },
    ],
  },
  {
    type: "BinaryLogic",
    title: "Binary Logic",
    category: "Logic",
    description: "Logical operations across two same-type model batches with optional scores.",
    inputs: [
      { key: "structures1", label: "Batch Protein (With Ligand) 1", type: "Batch Protein (With Ligand)" },
      { key: "score1", label: "Score1", type: "Score", optional: true },
      { key: "structures2", label: "Batch Protein (With Ligand) 2", type: "Batch Protein (With Ligand)" },
      { key: "score2", label: "Score2", type: "Score", optional: true },
    ],
    options: [{ key: "operation", label: "Operation", kind: "select", value: "OR", items: ["OR", "AND", "NOR", "NAND", "XOR"] }],
    outputs: [
      { key: "structures", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" },
      { key: "score", label: "Score", type: "Score" },
    ],
  },
  {
    type: "Protein2Seq",
    title: "Protein To Sequence",
    category: "Util",
    description: "Extract batch sequences from a batch protein input.",
    inputs: [{ key: "batchProtein", label: "Batch Protein", type: "Batch Protein" }],
    outputs: [{ key: "sequences", label: "Batch Sequence", type: "Batch Sequence" }],
  },
  {
    type: "Merge",
    title: "Merge",
    category: "Util",
    description: "Merge batch protein and batch/single ligand into complexes.",
    inputs: [
      { key: "ligand", label: "(Batch) Ligand", type: "Ligand" },
      { key: "batchProtein", label: "Batch Protein", type: "Batch Protein" },
    ],
    outputs: [{ key: "complexes", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" }],
  },
  {
    type: "Split",
    title: "Split",
    category: "Util",
    description: "Split complexes into ligand conformers and proteins.",
    inputs: [{ key: "complexes", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" }],
    outputs: [
      { key: "batchLigand", label: "Batch Ligand", type: "Batch Ligand" },
      { key: "batchProtein", label: "Batch Protein", type: "Batch Protein" },
    ],
  },
  {
    type: "PDBViewer",
    title: "PDB Viewer",
    category: "View",
    description: "Inspect batch protein or protein-ligand structures in a node-local 3D viewer.",
    inputs: [{ key: "structures", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" }],
    options: [{ key: "viewer", label: "File Selector + 3D Viewer", kind: "viewer", value: "Open", viewerMode: "batchStructure" }],
  },
  {
    type: "SequenceViewer",
    title: "Sequence Viewer",
    category: "View",
    description: "Inspect batch sequences from FASTA or generated designs.",
    inputs: [{ key: "sequences", label: "Batch Sequence", type: "Batch Sequence" }],
    options: [{ key: "file", label: "File Selector", kind: "text", value: "sequence_0001.fasta" }],
  },
  {
    type: "SaveProteinsWithScores",
    title: "Save Proteins with Scores",
    category: "Save",
    description: "Save protein PDB files and score CSV with a PDB filename column.",
    inputs: [
      { key: "structures", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" },
      { key: "score", label: "Score", type: "Score" },
    ],
    options: [{ key: "folder", label: "Folder Selector", kind: "text", value: "outputs/proteins" }],
  },
  {
    type: "SaveProteins",
    title: "Save Proteins",
    category: "Save",
    description: "Save protein PDB files without score CSV.",
    inputs: [{ key: "structures", label: "Batch Protein (With Ligand)", type: "Batch Protein (With Ligand)" }],
    options: [{ key: "folder", label: "Folder Selector", kind: "text", value: "outputs/proteins" }],
  },
  {
    type: "SaveSequences",
    title: "Save Sequences",
    category: "Save",
    description: "Save batch sequences as FASTA.",
    inputs: [{ key: "sequences", label: "Batch Sequence", type: "Batch Sequence" }],
    options: [{ key: "folder", label: "Folder Selector", kind: "text", value: "outputs/sequences" }],
  },
  {
    type: "SaveLigands",
    title: "Save Ligands",
    category: "Save",
    description: "Save ligand or batch ligand structures as PDB files.",
    inputs: [{ key: "ligand", label: "(Batch) Ligand", type: "Ligand" }],
    options: [{ key: "folder", label: "Folder Selector", kind: "text", value: "outputs/ligands" }],
  },
];
