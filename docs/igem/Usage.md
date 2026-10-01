# Using FoundryUI

FoundryUI represents a modelling protocol as a directed graph. Data enters through load nodes, passes through connected operations, and leaves through view or save nodes. The main concepts are nodes, types, runs, and artifacts.

[image of a labelled FoundryUI workflow identifying nodes, ports, connections, and the run bar]

## Core concepts

### Nodes

A node is one operation. Ports on the left receive inputs, ports on the right produce outputs, and controls inside the node define parameters. The node browser groups operations into Load, Selector, Generation, MPNN, Folding, Analysis, Filter, Logic, View, Save, and Note categories.

Click a node in the browser to add it, then drag between compatible ports. Optional inputs are marked with an asterisk. Note nodes document the graph but are not executed.

Load nodes start a workflow from a PDB or FASTA file. Generation, MPNN, and Folding nodes perform model-backed work. Selector, Analysis, Filter, and Logic nodes refine the design set. Viewer and Save nodes expose the outputs. Reading a graph from left to right therefore gives a concise description of the modelling protocol.

### Types

Types prevent biologically incompatible connections. FoundryUI distinguishes ligands, proteins, protein–ligand complexes, sequence batches, scores, residue lists, and atom selections. Batch ports support collections, while safe conversions allow operations such as using a single ligand across several folds.

Port colours provide immediate feedback, and the backend performs the final validation before a run. Ambiguous conversions and incompatible batch lengths are rejected instead of being silently accepted.

Batch behaviour is deliberate. Structures and their score rows stay aligned through filters. During RF3 co-folding, batch inputs are paired by index; a one-item sequence batch can be broadcast where valid, and a single ligand can be reused for every fold. A mismatch that cannot be resolved safely produces an error.

### Runs and sessions

Pressing **Run** validates and queues the current graph. The top bar shows state, progress, and completed nodes; the **Logs** panel streams model output; and the **Issues** panel identifies the node responsible for a validation or runtime error. Active runs can be stopped, and finished runs can be downloaded as archives.

A session stores the workflow and its latest run. If a node and its inputs have not changed, FoundryUI can reuse the previous output. This avoids repeating an expensive model call or manual selection.

The cache follows dependencies. Editing a downstream viewer does not require generation to run again, but changing a ligand input invalidates every dependent result. Cached nodes are indicated in the interface and can be cleared through the session API when a fresh calculation is required.

### Artifacts and saved results

An artifact is a registered file produced during a run, such as a PDB structure, FASTA sequence set, score table, or selection map. Artifacts use run-relative paths so saved workflows do not depend on a user's computer.

Save nodes mark the intended final outputs. The **Save** panel provides direct downloads, while the run archive also retains intermediate evidence for reproducibility and debugging.

The workflow and archive serve different purposes. A `.fuiworkflow` file is a portable recipe that can be edited and run with new inputs. A run archive is the evidence from one execution. For reproducible reporting, keep both together with the model and checkpoint versions.

## Working with the interface

### Manual selection

Residue and atom selector nodes pause when their input structure becomes available. Open the node's viewer, inspect the model, make the requested selection, and submit it to continue. The resulting typed selection can guide RFDiffusion3 constraints, MPNN positions, or structural filters.

[image of the 3D viewer with selected residues highlighted and a submit-selection control]

### A first workflow

1. **Connect.** Open the workbench and confirm that the API status is **available**.
2. **Choose a starting point.** Load one of the six supplied presets, or add a load node to an empty canvas.
3. **Provide data.** Upload the PDB or FASTA file requested by the load node.
4. **Build the protocol.** Add the required modelling, analysis, viewer, and save nodes, then connect matching ports.
5. **Review parameters.** Check batch sizes, seeds, thresholds, and model-specific options before using GPU time.
6. **Run.** Press **Run**. Static problems appear in **Issues** before the graph is queued.
7. **Respond to manual nodes.** If execution pauses, make the requested selection in the 3D viewer and submit it.
8. **Inspect evidence.** Follow model output in **Logs**, open generated structures, and compare score tables.
9. **Export.** Download saved results or the complete run archive, then save the `.fuiworkflow` protocol.

[image of the preset menu and the Run, Save Workflow, and Download Archive controls]

## Reusing and sharing work

### Workflow files and formats

The **N**, **S**, **L**, and **C** controls create a session, save a workflow, load a workflow, and clear the canvas. Presets provide editable starting points.

Use PDB for protein, ligand, and complex structures, and FASTA for sequences. Scores are written as JSON and CSV. Workflows use the JSON-based `.fuiworkflow` format, while multi-file results are downloaded as ZIP archives.

### Understanding errors

Validation errors identify the node, port, or option that must be corrected. Runtime errors include a code, message, and context such as the expected checkpoint path. Common causes are a missing required connection, an unsupported upload, unequal batch lengths, or an unavailable model executable.

Correct the reported node and run the workflow again. Completed upstream nodes may be reused if their inputs are unchanged. Command output remains available in the log, and produced artifacts remain in the run directory even when a later node fails.

[image of the Issues panel highlighting an invalid connection and linking it to the affected node]
