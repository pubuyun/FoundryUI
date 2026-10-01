# FoundryUI

FoundryUI is a visual programming environment for protein and protein–ligand modelling. It turns a multi-step design process into an executable graph: users connect nodes to load biomolecular data, select residues or atoms, generate structures, design sequences, predict folds, filter candidates, inspect models, and save results.

[image of the FoundryUI workbench showing a complete protein-design workflow]

## Overview

### Highlights

- Visual workflows for protein and ligand design
- RFDiffusion3, RosettaFold3, ProteinMPNN, and LigandMPNN integration
- Typed connections and pre-run graph validation
- Interactive 3D residue and atom selection
- Live logs, reusable sessions, and downloadable artifacts
- JSON API and an extensible node system

## From scripts to visual workflows

Inspired by ComfyUI, FoundryUI replaces one-off command sequences with reusable blocks. A connection means that one node's typed output becomes another node's input. The graph is both the user interface and a record of the computational protocol, so collaborators can understand, reproduce, and modify it.

Current workflows combine RFDiffusion3, RosettaFold3, ProteinMPNN, and LigandMPNN with input, selection, analysis, filtering, viewing, and saving nodes. Supplied presets cover small-molecule binders, protein binders, enzyme design, sequence design, and co-folding.

## Implementation

### A graphical modelling workbench

The Nuxt and Vue interface uses BaklavaJS for graph editing and 3Dmol.js for molecular visualization. Users can add nodes from a categorized browser, connect colour-coded ports, upload structures or sequences, edit model parameters, and follow execution through progress and log panels.

Manual selector nodes open an upstream structure in the 3D viewer and pause the run until the user submits a residue or atom selection. This makes expert judgement an explicit, reproducible part of the workflow.

[image of a residue or atom being selected in the FoundryUI 3D viewer]

### Typed and reproducible execution

Before execution, the FastAPI backend checks graph structure, required ports, option bounds, cycles, and type compatibility. RyvenCore executes the validated graph, while Server-Sent Events deliver live node status and command output to the browser.

Data moves between nodes as typed payloads with an item count, artifact identifiers, run-relative paths, and metadata. Intermediate files are retained, final outputs can be marked with save nodes, and a complete run can be downloaded as an archive. Sessions preserve workflows and can reuse unchanged node outputs.

[illustration of a workflow moving from browser graph to validation, model execution, and archived artifacts]

## Compatibility and reuse

### Standards and interoperability

FoundryUI uses common scientific data formats at its boundaries: PDB for structures, FASTA for sequences, mmCIF from RF3, SMILES for ligand representations, JSON and CSV for scores, and ZIP for result archives. Portable `.fuiworkflow` files store graphs as JSON. Biopython and RDKit provide biological and chemical parsing rather than relying on private formats.

Native SBOL import and export are not yet implemented. The typed architecture makes this a practical extension: an SBOL input node could translate components and sequences into FoundryUI payloads, while an export node could preserve designed sequences and run provenance in an SBOL document.

### Integration and reuse

FoundryUI wraps external models rather than reimplementing them. Each adapter converts node inputs into a tool's native command or files, streams its output, and registers the results for downstream use. Executable and checkpoint locations can be changed with environment variables, allowing the same workflow to run on a workstation, cloud GPU, or shared server.

The backend also exposes JSON APIs for catalog discovery, upload, validation, execution, live events, sessions, outputs, and archives. Other projects can therefore use FoundryUI through its GUI or integrate it into notebooks and automated services.

## Evidence and outlook

### Validation

Validation is applied to uploaded data, graph structure, runtime batch alignment, model outputs, and artifacts. The repository includes tests for API health, node registration, workflow validation, typed conversions, caching, selectors, filters, RMSD analysis, RF3 co-folding, command construction, and cancellation. Frontend types can be checked independently.

These tests evaluate FoundryUI's orchestration and data handling; they are not a new biological benchmark of the upstream models. Biological performance remains dependent on the chosen model, checkpoint, parameters, and experimental validation.

### Future teams

The frontend node catalog is generated from backend node definitions. A developer can add a focused operation while reusing the existing editor, validation, runtime, artifact storage, and session system. This makes FoundryUI useful both as a ready-to-run modelling interface and as a foundation for future synthetic biology software projects.
