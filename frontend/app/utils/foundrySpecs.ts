export type PortType = string;

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
  viewerMode?: "residue" | "atom" | "proteinAtom" | "chain" | "score" | "structure" | "batchStructure" | "sequence";
}

export interface FoundryNodeSpec {
  type: string;
  title: string;
  category: string;
  description: string;
  inputs?: PortSpec[];
  options?: OptionSpec[];
  outputs?: PortSpec[];
  requiresRuntimeInput?: boolean;
  hidden?: boolean;
  ui?: Record<string, any>;
}

export interface NodeCatalogResponse {
  version: number;
  types: Array<{ name: PortType; detail: string; color?: string }>;
  conversions: Array<{ from: PortType; to: PortType }>;
  nodes: FoundryNodeSpec[];
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
