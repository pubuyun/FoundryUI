# FoundryUI Backend Implementation Notes

This document records frontend assumptions and backend requirements for the Rosetta Foundry visual workflow.

## Backend Stack

- API: FastAPI.
- Visual execution: Ryvencore.
- Task management: `asyncio.Queue`.
- Bioinformatics: Biopython and RDKit.
- Workflow domain: RFdiffusion3/RosettaFold3 small molecule protein binder design.

## Frontend Contract

The frontend is a Nuxt/Vue/BaklavaJS visual graph editor. The backend should accept a serialized workflow graph containing:

- Nodes: `type`, `id`, `title`, `inputs`, `outputs`, and option interface values.
- Connections: source node/interface id to target node/interface id.
- Uploaded structures: PDB/SDF/FASTA file contents associated with input node ids.
- Execution request metadata: selected workflow id/session id, task parameters, and optional run name.

Do not treat node options as graph inputs. Options are node-local controls and must be read from the node option values. Actual workflow data moves through typed ports only.

Saved workflows use `.fuiworkflow` JSON files. The current file shape is:

- `fileType: "FoundryUIWorkflow"`
- `version`
- `savedAt`
- `baklava`: native Baklava editor state for frontend reloads.
- `workflow`: backend-friendly normalized graph.
- `uploads`: uploaded file contents grouped by frontend node id.

Prefer the `workflow` object for backend execution. It contains stable node ids, node types, option values, typed inputs/outputs, and connections by node id plus interface key. The `baklava` object is primarily a frontend restore format and contains renderer/editor details that the backend should not depend on.

## Types

Backend types must match `Types.md`:

- `Ligand`: single small molecule structure, PDB or SDF.
- `Protein`: single protein PDB.
- `List of Residues`: string/list such as `A58,A102`.
- `List of Atoms`: string/list such as `C1,C2`.
- `Batch Protein`: list of protein PDB models.
- `Batch Ligand`: list of ligand conformers.
- `Batch Protein with Ligand`: list of protein-ligand complex PDB models.
- `Batch Sequence`: list of sequences from FASTA or model design.
- `Score`: list of dictionaries with score fields.

When `Batch Protein` or `Batch Ligand` connects to a single `Protein` or `Ligand` input, use only the first item.

## Node Semantics

Important nodes and backend behavior:

- `LigandInput`: accepts SMILES text or uploaded PDB/SDF. If SMILES is used, backend must generate/validate a ligand structure before downstream 3D tasks.
- `ProteinInput`: accepts uploaded PDB files and emits `Batch Protein`.
- `SequenceInput`: accepts uploaded FASTA and emits `Batch Sequence`.
- `ResidueSelector`: emits residue IDs. If the input is missing, use the manually typed text.
- `AtomSelector`: emits atom IDs. If the input is missing, use the manually typed text.
- `RFDiffusionSMbinder`: inputs `Ligand`, `select_fixed_atoms`, `select_buried`, and `select_exposed`. The three selector inputs are type `List of Atoms`; if disconnected, backend should treat them as empty strings/lists. Options are `length`, `n_batches`, and `diffusion_batch_size`.
- `LigandMPNN` / `ProteinMPNN`: input `residues` is interpreted according to option `residueRole`, either `fixed_residues` or `redesigned_residues`. Required options are `number_of_batches` and `batch_size`; defaulted options are `seed=42`, `temperature=0.05`, `bias_AA=""`, and `omit_AA=""`.
- `RosettaFold3`: inputs `Batch Sequence` and optional `Ligand`; options are `early_stopping_plddt_threshold=0.5`, `diffusion_batch_size=5`, `num_steps=50`, `seed=42`.
- `FilterByScore`: must filter structures and scores together, preserving aligned order.
- `FilterChirality`: filters complexes by configured atom/chirality pairs such as `C0:S, C4:R`. Optional scores must stay aligned; if no score input is connected, do not emit a score output.
- `BinaryLogic`: both structure inputs must be the same effective type. Optional scores must stay aligned with their corresponding structures.
- `Protein2Seq`: extracts sequences from batch protein PDBs.
- `Merge`: supports merging one ligand into all batch proteins or merging batch ligand conformers with batch proteins.
- `Split`: emits `Batch Ligand` and `Batch Protein`.
- `PDBViewer` and `SequenceViewer`: frontend-only display nodes for now; backend can treat them as terminal sinks unless result materialization is required.
- `SaveProteinsWithScores`: terminal save node. Input `structures` is `Batch Protein (With Ligand)`; input `score` is required. Write each structure as a PDB file and write scores as CSV. CSV must include one column that maps each score row to the corresponding PDB filename.
- `SaveSequences`: terminal save node. Input `sequences` is `Batch Sequence`. Write a FASTA file or one FASTA per sequence, depending on backend artifact policy.
- `SaveLigands`: terminal save node. Input `ligand` accepts `Ligand` and, via conversion, `Batch Ligand`. Write ligand structures as PDB files.

## Score Handling

Scores are lists aligned 1:1 with model batches. Backend must not reorder structures without making the same transformation to score lists.

Expected score keys:

- `pLDDT`
- `length`
- `pTM`
- `interface_PAE`
- `ipTM`
- `ranking_score`

Ligand-specific score keys may be absent when no ligand co-folding occurred.

## File Handling

Backend should store uploads per run/session and map them by frontend node id. Required validation:

- PDB: parseable protein/complex structure.
- SDF: parseable small molecule.
- FASTA: one or more valid sequences.
- SMILES: parseable by RDKit and convertible to a ligand structure.

Large files should not be sent repeatedly with every graph run after upload. Prefer upload endpoints returning file handles, then submit workflow graph with file handles.

Browser folder selection does not provide a real backend filesystem path. The current frontend exposes save-node folder selectors as text options such as `outputs/proteins`. Backend should treat these as run-relative artifact directories unless a future desktop/local-agent mode provides trusted absolute paths.

## API Plan

Suggested endpoints:

- `POST /api/uploads`: upload structure/sequence files; returns file ids and metadata.
- `POST /api/workflows/validate`: validate graph topology, types, required options, and file availability.
- `POST /api/runs`: enqueue workflow execution; returns task id.
- `GET /api/runs/{task_id}`: return state, current node, progress, warnings, and errors.
- `GET /api/runs/{task_id}/events`: SSE stream for progress/log updates.
- `GET /api/runs/{task_id}/artifacts`: list produced models, sequences, scores, and logs.
- `GET /api/artifacts/{artifact_id}`: download a generated artifact.
- `GET /api/runs/{task_id}/archive`: optional endpoint to download all save-node outputs as a ZIP.

## Execution Model

Convert the Baklava graph into a Ryvencore graph:

1. Validate all node types and ports.
2. Resolve typed connections and allowed conversions.
3. Load uploaded files/SMILES into internal typed objects.
4. Run nodes in topological order unless Ryvencore handles scheduling.
5. Store every node output as an artifact or intermediate object with type metadata.
6. Stream progress and per-node logs back to the frontend.

## Failure Reporting

Return structured errors with:

- `node_id`
- `node_type`
- `interface_key` or `option_key` when relevant
- `message`
- `recoverable`
- optional traceback/log artifact id

The frontend can highlight failed nodes once these fields are available.

## Notes From Frontend Behavior

- Atom selector uses 3Dmol clickable atom callbacks and writes a comma-separated atom list into the node option value.
- Residue selector follows the same option-value model with residue IDs.
- Ligand input hides SMILES/file/viewer controls based on source mode, but backend must still validate source consistency.
- Viewer buttons are frontend-local and should not create backend execution steps unless the workflow explicitly needs materialized previews.
