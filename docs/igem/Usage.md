# Using FoundryUI

FoundryUI represents a modelling protocol as a directed graph. Data enters through load nodes, passes through connected operations, and leaves through view or save nodes. The main concepts are nodes, types, runs, and artifacts.

[image of a labelled FoundryUI workflow identifying nodes, ports, connections, and the run bar]

## Core concepts

### Nodes

A node is one operation. Ports on the left receive inputs, ports on the right produce outputs, and controls inside the node define parameters. The node browser groups operations into Load, Selector, Generation, MPNN, Folding, Analysis, Filter, Logic, View, Save, and Note categories.

Click a node in the browser to add it, then drag between compatible ports. Optional inputs are marked with an asterisk. Note nodes document the graph but are not executed.

### Types

Types prevent biologically incompatible connections. FoundryUI distinguishes ligands, proteins, protein–ligand complexes, sequence batches, scores, residue lists, and atom selections. Batch ports support collections, while safe conversions allow operations such as using a single ligand across several folds.

Port colours provide immediate feedback, and the backend performs the final validation before a run. Ambiguous conversions and incompatible batch lengths are rejected instead of being silently accepted.

### Runs and sessions

Pressing **Run** validates and queues the current graph. The top bar shows state, progress, and completed nodes; the **Logs** panel streams model output; and the **Issues** panel identifies the node responsible for a validation or runtime error. Active runs can be stopped, and finished runs can be downloaded as archives.

A session stores the workflow and its latest run. If a node and its inputs have not changed, FoundryUI can reuse the previous output. This avoids repeating an expensive model call or manual selection.

### Artifacts and saved results

An artifact is a registered file produced during a run, such as a PDB structure, FASTA sequence set, score table, or selection map. Artifacts use run-relative paths so saved workflows do not depend on a user's computer.

Save nodes mark the intended final outputs. The **Save** panel provides direct downloads, while the run archive also retains intermediate evidence for reproducibility and debugging.

## Working with the interface

### Manual selection

Residue and atom selector nodes pause when their input structure becomes available. Open the node's viewer, inspect the model, make the requested selection, and submit it to continue. The resulting typed selection can guide RFDiffusion3 constraints, MPNN positions, or structural filters.

[image of the 3D viewer with selected residues highlighted and a submit-selection control]

### A first workflow

1. Open the workbench and confirm that the API status is **available**.
2. Load a preset or add a load node and upload a PDB or FASTA file.
3. Add the desired modelling, analysis, viewer, and save nodes.
4. Connect matching ports and configure node options.
5. Press **Run** and correct any issue highlighted on the graph.
6. Complete manual selections if the workflow pauses.
7. Inspect logs and structures, then download saved outputs or the complete archive.
8. Save the `.fuiworkflow` file so the protocol can be reused.

[image of the preset menu and the Run, Save Workflow, and Download Archive controls]

## Reusing and sharing work

### Workflow files and formats

The **N**, **S**, **L**, and **C** controls create a session, save a workflow, load a workflow, and clear the canvas. Presets provide editable starting points.

Use PDB for protein, ligand, and complex structures, and FASTA for sequences. Scores are written as JSON and CSV. Workflows use the JSON-based `.fuiworkflow` format, while multi-file results are downloaded as ZIP archives.
