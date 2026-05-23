# FoundryUI Backend Build Plan

This plan defines the backend implementation for executing `.fuiworkflow` graphs exported by the Nuxt/Vue/BaklavaJS frontend. The backend must use the normalized `workflow` object from `.fuiworkflow` files, not Baklava renderer/editor state.

## Goals

- Provide a FastAPI service for uploads, workflow validation, queued execution, live run feedback, artifact listing, artifact downloads, and run archives.
- Execute workflows with Ryvencore-compatible graph semantics while preserving the frontend node and type contract.
- Store every intermediate and final result as a persistent run artifact.
- Stream progress and command output to the frontend with Server-Sent Events.
- Return structured validation and runtime errors that can be mapped back to nodes, ports, and options.

## Stack

- API: FastAPI.
- Visual workflow execution: Ryvencore.
- Queue/runtime: in-memory `asyncio.Queue` for the initial implementation.
- Bioinformatics parsing/conversion: Biopython and RDKit.
- External tools: Foundry CLI wrappers for `rfd3`, `rf3`, LigandMPNN, and ProteinMPNN.
- Artifact storage: local run directories under `backend/runs/{run_id}/`.

## Target Backend Layout

```text
backend/
  main.py
  schemas/
    workflow.py
    payloads.py
    artifacts.py
    events.py
    errors.py
  workflow/
    validation.py
    graph.py
    ryvencore_adapter.py
    type_conversions.py
  nodes/
    inputs.py
    selectors.py
    generation.py
    mpnn.py
    folding.py
    filters.py
    logic.py
    utils.py
    viewers.py
    save.py
  runtime/
    queue.py
    registry.py
    runner.py
    events.py
    subprocesses.py
  artifacts/
    store.py
    registry.py
    archive.py
  bio/
    pdb.py
    ligand.py
    fasta.py
    sequences.py
  foundry_tools/
    rfd3.py
    rf3.py
    ligand_mpnn.py
    protein_mpnn.py
```

## FastAPI Routers

Expand `backend/main.py` into an application that mounts routers for:

- `uploads`: file upload and parse validation.
- `workflow validation`: graph, node, port, option, and type validation.
- `run queue`: enqueue workflow runs.
- `run status/events`: status snapshots and SSE event streams.
- `artifacts/downloads`: artifact listing, single artifact download, and run archive download.

Required endpoints:

- `POST /api/uploads`
- `POST /api/workflows/validate`
- `POST /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `GET /api/runs/{run_id}/artifacts`
- `GET /api/artifacts/{artifact_id}`
- `GET /api/runs/{run_id}/archive`

Keep `GET /health` for smoke checks.

## Data Model

Create Pydantic schemas for:

- `.fuiworkflow` files:
  - `fileType`
  - `version`
  - `savedAt`
  - `workflow`
  - `uploads`
  - optional `baklava`, accepted for frontend reloads but ignored during execution.
- Normalized workflow graph:
  - node id
  - node type
  - title
  - option values
  - typed inputs
  - typed outputs
  - connections by node id and interface key.
- Runtime payloads:
  - typed values for `Ligand`, `Protein`, `List of Residues`, `List of Atoms`, `Batch Protein`, `Batch Ligand`, `Batch Protein with Ligand`, `Batch Sequence`, and `Score`.
- Artifact metadata:
  - artifact id
  - run id
  - node id
  - node type
  - payload type
  - media/file type
  - run-relative path
  - byte size
  - item count
  - created timestamp
  - metadata for downstream nodes.
- Run status:
  - `state`
  - `current_node_id`
  - `current_node_type`
  - `completed_nodes`
  - `total_nodes`
  - `progress_percent`
  - recent command output lines
  - structured warnings
  - structured errors.
- Events:
  - `queued`
  - `started`
  - `node_started`
  - `node_progress`
  - `stdout`
  - `stderr`
  - `node_completed`
  - `artifact_created`
  - `warning`
  - `error`
  - `completed`.
- Errors:
  - `run_id`
  - `node_id`
  - `node_type`
  - `interface_key`
  - `option_key`
  - `code`
  - `message`
  - `details`
  - `recoverable`
  - `log_artifact_id`.

## Artifact Storage Policy

Every run must have a persistent directory:

```text
backend/runs/{run_id}/
  uploads/
  nodes/
    {node_id}_{node_type}/
  saves/
  logs/
  archive.zip
  manifest.json
```

Every node must write outputs under:

```text
backend/runs/{run_id}/nodes/{node_id}_{node_type}/
```

Intermediate output requirements:

- `Batch Protein`: store each structure as PDB.
- `Batch Protein with Ligand`: store each complex as PDB.
- `Batch Ligand`: store each ligand conformer as PDB.
- `Batch Sequence`: store FASTA.
- `Score`: store JSON and CSV where practical.
- `List of Atoms`: store JSON.
- `List of Residues`: store JSON.
- Command logs: store stdout/stderr log artifacts when external commands run.

Each node handler must return a typed payload containing:

- type name
- item count
- artifact ids
- file paths relative to `backend/runs/{run_id}/`
- metadata needed by downstream nodes.

Save nodes must copy or export from intermediate artifacts into run-relative save folders:

- `SaveProteinsWithScores`: PDB files plus a score CSV containing a `pdb_filename` column.
- `SaveSequences`: FASTA.
- `SaveLigands`: PDB files.

Browser folder selectors are not trusted filesystem paths. Treat save-node folder options as run-relative paths under `backend/runs/{run_id}/saves/`.

## Upload And File Validation

`POST /api/uploads` must accept PDB, SDF, FASTA, and SMILES-related inputs and return upload/file ids that workflows can reference later.

Validate before accepting an upload for execution:

- PDB: parse with Biopython and reject unparseable structures.
- SDF: parse with RDKit and reject empty or invalid molecules.
- SMILES: parse with RDKit and verify it can be converted into a ligand structure.
- FASTA: parse with Biopython or a strict FASTA parser and require at least one valid sequence.

Large files should be uploaded once and referenced by id in run requests instead of being resent with every workflow.

## Workflow Validation

Validate `.fuiworkflow.workflow` only. Do not validate or execute the Baklava renderer state.

Reject:

- unknown node types
- unknown input or output ports
- missing required inputs
- disconnected required ports
- invalid option values
- missing required options
- invalid type conversions
- cycles
- structure/score length mismatches
- incompatible inputs to logic nodes
- missing upload/file handles.

Allowed conversion:

- `Batch Protein` to `Protein`: use the first item.
- `Batch Ligand` to `Ligand`: use the first item.

Node options are node-local controls, not graph inputs. Data only moves through typed ports.

## Runtime Model

Use an in-memory `asyncio.Queue` for initial run scheduling:

1. `POST /api/runs` validates the workflow and uploads.
2. A run id is created and a run directory is initialized.
3. The run request is enqueued.
4. A background worker pulls queued runs.
5. The runner builds a normalized executable graph and adapts it to Ryvencore where useful.
6. Nodes execute in topological order or through Ryvencore scheduling.
7. Each node writes persistent artifacts before returning its typed payload.
8. Runtime state and events are published to the run registry.
9. Terminal save nodes materialize final outputs.
10. The run is marked completed or failed.

The run registry must retain status, recent stdout/stderr lines, warning/error lists, artifact metadata, and event history sufficient for late SSE subscribers to catch up.

## Live Feedback

Use Server-Sent Events from `GET /api/runs/{run_id}/events`.

The SSE stream must emit JSON event payloads for:

- queue state
- run start/completion
- node start/progress/completion
- command stdout/stderr
- artifact creation
- warnings
- structured errors.

Subprocess wrappers must stream stdout and stderr line-by-line into the event system while also writing log artifacts. Run status must expose recent command output so the frontend can show live logs and progress even without reading the full log file.

## Structured Errors

All validation and runtime failures must use the structured error schema:

```json
{
  "run_id": "run_...",
  "node_id": "node_...",
  "node_type": "RosettaFold3",
  "interface_key": "structures",
  "option_key": null,
  "code": "SCORE_LENGTH_MISMATCH",
  "message": "Structure and score list lengths do not match.",
  "details": {
    "input_keys": ["structures", "score"],
    "expected_length": 12,
    "actual_length": 10
  },
  "recoverable": false,
  "log_artifact_id": "artifact_..."
}
```

Validation errors should identify the node and interface or option whenever possible so the frontend can highlight the failed element.

## Score Alignment Rules

Scores are lists aligned 1:1 with model batches.

- Whenever structures and scores are both present, require `len(batch_structures) == len(score_list)`.
- If lengths mismatch, fail with node id, node type, input keys, expected length, and actual length.
- Filtering and logic nodes must transform structures and scores together.
- Nodes with optional score inputs must not emit score outputs when the optional score input is not connected.
- Any node that changes model count or order must apply the identical transformation to scores.

## Node Implementation Plan

### Inputs And Selectors

- `LigandInput`
  - Accept SMILES or uploaded PDB/SDF.
  - Validate with RDKit/Biopython as appropriate.
  - Emit `Ligand`.
  - Save normalized PDB artifact.
- `ProteinInput`
  - Accept uploaded PDB files.
  - Emit `Batch Protein`.
  - Save normalized PDB artifacts.
- `SequenceInput`
  - Accept uploaded FASTA.
  - Emit `Batch Sequence`.
  - Save FASTA artifact.
- `AtomSelector`
  - Accept optional `Ligand` input and manual selector text.
  - Emit `List of Atoms`.
  - Save JSON list artifact.
- `ResidueSelector`
  - Accept optional `Protein` input and manual selector text.
  - Emit `List of Residues`.
  - Save JSON list artifact.

### Generation And Design

- `RFDiffusionSMbinder`
  - Inputs: `Ligand`, `select_fixed_atoms`, `select_buried`, `select_exposed`.
  - Treat disconnected selector inputs as empty lists.
  - Options: `length`, `n_batches`, `diffusion_batch_size`.
  - Run `rfd3 design`.
  - Stream stdout/stderr.
  - Emit `Batch Protein with Ligand`.
  - Save generated complexes as PDB files.
- `LigandMPNN`
  - Input: `Batch Protein with Ligand`.
  - Residue selector input is interpreted by option `residueRole` as fixed or redesigned residues.
  - Options: `number_of_batches`, `batch_size`, `seed`, `temperature`, `bias_AA`, `omit_AA`.
  - Emit `Batch Sequence` and optional designed structures if produced by the tool.
  - Save FASTA and any generated PDB artifacts.
- `ProteinMPNN`
  - Input: `Batch Protein`.
  - Use the same `residueRole` handling as `LigandMPNN`.
  - Emit `Batch Sequence`.
  - Save FASTA artifact.
- `RosettaFold3`
  - Inputs: `Batch Sequence` and optional `Ligand`.
  - Options: `early_stopping_plddt_threshold`, `diffusion_batch_size`, `num_steps`, `seed`.
  - Run `rf3 fold`.
  - Emit `Batch Protein` or `Batch Protein with Ligand` plus `Score`.
  - Save PDB batch plus score JSON/CSV.

### Filters, Logic, And Utilities

- `FilterByScore`
  - Accept `Batch Protein` or `Batch Protein with Ligand` plus `Score`.
  - Support score keys `pLDDT`, `length`, `pTM`, `interface_PAE`, `ipTM`, and `ranking_score`.
  - Support largest top N, smallest top N, higher than value, and lower than value.
  - Emit filtered structures and filtered scores in the same order.
- `FilterByLigand`
  - Accept `Batch Protein with Ligand`, `Ligand`, and optional `Score`.
  - Support chirality-sensitive or chirality-insensitive matching.
  - Emit filtered complexes and emit score only when score input is connected.
- `BinaryLogic`
  - Require both structure inputs to have the same effective type.
  - Support `OR`, `AND`, `NOR`, `NAND`, and `XOR`.
  - Preserve optional score alignment for each structure set.
- `Protein2Seq`
  - Extract sequences from `Batch Protein`.
  - Emit `Batch Sequence`.
- `Merge`
  - Merge `Batch Protein` with a single `Ligand` or `Batch Ligand`.
  - Emit `Batch Protein with Ligand`.
- `Split`
  - Split `Batch Protein with Ligand`.
  - Emit `Batch Protein` and `Batch Ligand`.

### View And Save Nodes

- `PDBViewer`
  - Treat as a no-op terminal node.
  - Optionally register existing PDB artifacts for frontend inspection.
- `SequenceViewer`
  - Treat as a no-op terminal node.
  - Optionally register existing FASTA artifacts for frontend inspection.
- `SaveProteinsWithScores`
  - Require structures and score.
  - Validate structure/score length alignment.
  - Write PDB files and `scores.csv` with `pdb_filename`.
- `SaveSequences`
  - Write FASTA into the save-node output folder.
- `SaveLigands`
  - Accept `Ligand` or `Batch Ligand`.
  - Write PDB files into the save-node output folder.

## Foundry Tool Wrappers

Create one wrapper module per external command:

- `foundry_tools/rfd3.py`
- `foundry_tools/rf3.py`
- `foundry_tools/ligand_mpnn.py`
- `foundry_tools/protein_mpnn.py`

Each wrapper must:

- build argument lists without shell interpolation
- run with `asyncio.create_subprocess_exec`
- stream stdout/stderr line-by-line into run events
- write stdout/stderr log artifacts
- return parsed artifact metadata
- convert non-zero exits into structured runtime errors with a log artifact id.

## Implementation Order

1. Define schemas for workflow files, normalized graph objects, typed payloads, artifacts, events, run status, and structured errors.
2. Implement run directory creation and artifact registry/manifest writing.
3. Implement upload endpoint and PDB/SDF/FASTA/SMILES validation.
4. Implement workflow validation, including node catalog, required ports/options, type conversion rules, cycle checks, and disconnected required port detection.
5. Implement queue, run registry, runner skeleton, and SSE event streaming.
6. Implement lightweight node handlers for inputs, selectors, viewers, and basic utilities.
7. Implement save nodes and run ZIP archive creation.
8. Implement Foundry subprocess wrappers with stdout/stderr streaming and log artifacts.
9. Implement `RFDiffusionSMbinder`, `LigandMPNN`, `ProteinMPNN`, and `RosettaFold3`.
10. Implement filtering/logic nodes and all score alignment checks.
11. Add unit, API, runtime, and slow/manual tests.
12. Wire the frontend run button, validation UI, SSE log/progress display, artifact list, and archive download later.

## Test Plan

Unit tests:

- schema parsing for `.fuiworkflow`
- node type and port validation
- required input and required option validation
- type conversion validation
- cycle detection
- disconnected required port detection
- PDB parsing
- SDF parsing
- FASTA parsing
- SMILES parsing and ligand conversion
- artifact registry and manifest persistence
- structure/score length checks
- score-preserving filter behavior
- optional score behavior when score input is disconnected.

API tests:

- `POST /api/uploads`
- `POST /api/workflows/validate`
- `POST /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `GET /api/runs/{run_id}/artifacts`
- `GET /api/artifacts/{artifact_id}`
- `GET /api/runs/{run_id}/archive`.

Runtime tests:

- queued run transitions from queued to running to completed
- mocked subprocess success
- mocked subprocess failure
- stdout event emission
- stderr event emission
- node failure stops the run with structured error
- all intermediate outputs are saved in expected formats
- save nodes materialize files from intermediate artifacts.

Slow/manual tests:

- real `rfd3 design` smoke run with tiny input
- real LigandMPNN smoke run
- real ProteinMPNN smoke run
- real `rf3 fold` smoke run
- end-to-end workflow with upload, validation, execution, SSE progress, artifact listing, artifact download, and archive download.

## Assumptions

- Run artifacts are local files under `backend/runs/{run_id}/`.
- Artifact paths exposed through APIs are run-relative and never trusted browser filesystem paths.
- Intermediate structural outputs are always normalized to PDB, including `Batch Protein with Ligand`.
- Initial queue state is in memory; durable scheduling can be added later without changing the API contract.
- Subprocess wrappers are preferred first because reference scripts and CLI commands already exist.
- Ryvencore integration should preserve the normalized frontend graph contract instead of leaking Ryvencore-specific details into API payloads.
