# FoundryUI Backend Structure

This backend is a FastAPI service that receives normalized FoundryUI workflow documents, validates them, queues graph executions, runs nodes through Ryvencore data flow, stores every intermediate artifact, and streams run feedback back to the frontend.

## Top-Level Modules

- `backend/main.py`
  - FastAPI app and HTTP API.
  - Accepts uploads, workflow validation requests, run creation, stop requests, manual-node input, status queries, SSE events, artifacts, archives, and sessions.

- `backend/schemas/`
  - Pydantic request/response and runtime models.
  - Important models:
    - `FoundryWorkflowDocument`: full `.fuiworkflow` document with `workflow`, optional `baklava`, and embedded `uploads`.
    - `WorkflowGraph`: normalized executable graph, containing `nodes` and `connections`.
    - `WorkflowNode`: backend node record with `id`, `type`, `inputs`, `options`, and `outputs`.
    - `TypedPayload`: the object passed between nodes.
    - `RunEvent` and `RunStatus`: SSE/status payloads sent to the frontend.
    - `ArtifactMetadata`: metadata for every stored file.

- `backend/workflow/`
  - `catalog.py`: backend node/port/option specification.
  - `validation.py`: validates graph shape, required ports, type compatibility, cycles, options, and multiple connections.
  - `type_conversions.py`: converts compatible payload types.
  - `ryvencore_adapter.py`: converts the normalized graph into a Ryvencore `Session` and `Flow`.

- `backend/runtime/`
  - `queue.py`: in-memory `asyncio.Queue` for run requests.
  - `runner.py`: starts a run, invokes the Ryvencore adapter, and catches structured errors.
  - `registry.py`: in-memory run state, events, subscribers, outputs, pending manual input, cache keys, and cancellation.
  - `subprocesses.py`: streams stdout/stderr from external tools into run events.
  - `sessions.py`: saved frontend session documents.
  - `uploads.py`: uploaded file storage for upload-id based workflows.

- `backend/artifacts/`
  - `store.py`: creates run/node folders, writes files, registers artifact metadata.
  - `archive.py`: creates run ZIP archives.
  - `registry.py`: global `artifact_store`.

- `backend/nodes/`
  - One Python handler layer for frontend node types.
  - `dispatch.py` maps node type strings to handler functions.
  - Handlers receive `ExecutionContext`, `WorkflowNode`, and input `TypedPayload`s.
  - Handlers return output-key to `TypedPayload` mappings.

- `backend/bio/`
  - PDB, ligand, FASTA, and sequence helpers.
  - Uses Biopython and RDKit for validation, parsing, conversion, chirality checks, RMSD, and ligand standardization.

- `backend/foundry_tools/`
  - Wrappers for external Foundry/RF3/RFD3/MPNN commands.
  - Commands are run as subprocesses with stdout/stderr event streaming.

## Main Data Objects

### Workflow Input

The backend executes `FoundryWorkflowDocument.workflow`, not the Baklava renderer state.

```json
{
  "fileType": "FoundryUIWorkflow",
  "workflow": {
    "nodes": [
      {
        "id": "node-id",
        "type": "LigandInput",
        "inputs": {},
        "options": { "file": "upload-id-or-file-name" },
        "outputs": { "ligand": { "type": "Ligand" } }
      }
    ],
    "connections": [
      {
        "from": { "nodeId": "source-id", "key": "output-key" },
        "to": { "nodeId": "target-id", "key": "input-key" }
      }
    ]
  },
  "uploads": {
    "node-id": [
      { "name": "input.pdb", "type": "pdb", "content": "PDB text..." }
    ]
  }
}
```

### Node Payloads

Every edge in the executable graph carries a `TypedPayload`.

```json
{
  "type_name": "Batch Protein with Ligand",
  "item_count": 5,
  "artifact_ids": ["artifact_..."],
  "paths": ["nodes/node_Type/file.pdb"],
  "metadata": { "effective_type": "Batch Protein with Ligand" },
  "data": ["optional in-memory data or file text"]
}
```

The important rule is that downstream nodes use run-relative `paths` and `artifact_ids`; they do not trust browser filesystem paths.

### Events Sent To The Frontend

Events are sent over `GET /api/runs/{run_id}/events` as Server-Sent Events.

Common event names:

- `queued`
- `started`
- `node_started`
- `node_progress`
- `stdout`
- `stderr`
- `input_required`
- `artifact_created`
- `node_completed`
- `warning`
- `error`
- `completed`
- `stopped`

Each event has:

```json
{
  "event": "node_started",
  "run_id": "run_...",
  "sequence": 12,
  "timestamp": "...",
  "node_id": "node-id",
  "node_type": "RosettaFold3",
  "message": "...",
  "data": {}
}
```

## Execution Flow

### 1. Upload Files

Endpoint:

```text
POST /api/uploads
```

Receives either multipart files or JSON:

```json
{
  "files": [
    { "name": "protein.pdb", "type": "pdb", "content": "..." }
  ]
}
```

Backend actions:

1. Detects file type from extension if needed.
2. Validates:
   - PDB with Biopython parser.
   - FASTA with backend FASTA parser.
3. Stores the file in `backend/uploads/`.
4. Returns upload IDs.

Sends:

```json
{
  "files": [
    {
      "file_id": "upload_...",
      "name": "protein.pdb",
      "type": "pdb",
      "size": 12345
    }
  ]
}
```

The frontend can also embed upload contents directly in the workflow document, so `/api/uploads` is optional for execution.

### 2. Validate Workflow

Endpoint:

```text
POST /api/workflows/validate
```

Receives either:

- full `FoundryWorkflowDocument`,
- `{ "document": FoundryWorkflowDocument }`,
- `{ "workflow": WorkflowGraph }`,
- or raw `WorkflowGraph`.

Backend actions:

1. Extracts `WorkflowGraph`.
2. Runs `validate_workflow`.
3. Checks:
   - unknown node types,
   - unknown input/output ports,
   - invalid option values,
   - invalid numeric option bounds,
   - cycles,
   - unknown connection endpoints,
   - invalid type conversions,
   - multiple connections to non-batch inputs,
   - disconnected required ports.

Sends:

```json
{
  "valid": true,
  "errors": [],
  "warnings": [],
  "node_count": 10,
  "connection_count": 9
}
```

Errors are structured and include fields such as `node_id`, `node_type`, `interface_key`, `option_key`, `code`, `message`, and `details`.

### 3. Create A Run

Endpoint:

```text
POST /api/runs
```

Receives `RunCreateRequest`:

```json
{
  "document": { "...": "FoundryWorkflowDocument" },
  "session_id": "session_...",
  "previous_run_id": "run_..."
}
```

Backend actions:

1. Extracts `WorkflowGraph`.
2. Runs graph validation again.
3. Validates input-node files:
   - `LigandInput`: requires PDB.
   - `ProteinInput`: requires PDB.
   - `ProteinWithLigandInput`: requires PDB.
   - `SequenceInput`: requires FASTA.
4. If a session has a previous run, injects `previous_run_id` for cache reuse.
5. Creates `run_id`.
6. Initializes run folders:

```text
backend/runs/{run_id}/
  uploads/
  nodes/
  saves/
  logs/
```

7. Creates a `RunRecord` in `run_registry`.
8. Starts the worker task if needed.
9. Puts `QueuedRun(run_id, request)` into `run_queue`.

Sends:

```json
{
  "accepted": true,
  "run_id": "run_...",
  "state": "queued"
}
```

If rejected, sends:

```json
{
  "accepted": false,
  "errors": [
    { "code": "MISSING_LIGAND_FILE", "message": "...", "node_id": "..." }
  ]
}
```

Also publishes SSE:

```text
queued
```

### 4. Worker Picks The Run

Code path:

```text
main._worker_loop
  -> runtime.runner.run_workflow
```

Receives from queue:

```python
QueuedRun(run_id="run_...", request=RunCreateRequest(...))
```

Backend actions:

1. Validates the graph again.
2. Checks cancellation before starting.
3. Marks run started in `run_registry`.
4. Publishes SSE:

```text
started
```

5. Runs `execute_ryvencore_workflow` in a background thread because Ryvencore execution is synchronous.

### 5. Build The Ryvencore Flow

Code path:

```text
workflow.ryvencore_adapter.execute_ryvencore_workflow
```

Receives:

- `run_id`
- full `RunCreateRequest`
- embedded uploads from the document/request.

Backend actions:

1. Creates `ExecutionContext`:

```python
ExecutionContext(
  run_id=run_id,
  store=artifact_store,
  registry=run_registry,
  uploads=request.embedded_uploads()
)
```

2. Creates a Ryvencore `Session`.
3. Registers `FoundryPayloadData`, a Ryvencore `Data` wrapper around `TypedPayload`.
4. Creates a Ryvencore `Flow` in data mode.
5. For every `WorkflowNode`, creates a dynamic subclass of `FoundryRyvencoreNode`.
6. Each generated Ryvencore node has:
   - input sockets from backend `NodeSpec.inputs`,
   - output sockets from backend `NodeSpec.outputs`,
   - references to the original `WorkflowNode`,
   - the execution context,
   - connected input metadata.
7. Registers node classes in the Ryvencore session.
8. Creates nodes in the Ryvencore flow.
9. Connects flow nodes based on workflow connections.

Multiple connected lines to a batch input become multiple Ryvencore input sockets for the same logical input key. The adapter combines payloads for that logical key before the handler runs.

### 6. Start Source Nodes

After connections are created, the adapter starts nodes with no connected inputs:

```python
flow_nodes[workflow_node.id].update()
```

Ryvencore then propagates output data through the graph. Downstream nodes execute automatically when their required inputs are available.

### 7. Execute One Node

Code path:

```text
FoundryRyvencoreNode.update_event
```

Receives from Ryvencore:

- zero or more `FoundryPayloadData` inputs.

Converts them to:

```python
dict[str, TypedPayload]
```

Backend actions for each node:

1. Check whether all required inputs are ready.
2. Check cancellation.
3. Compute a node cache key from:
   - node type,
   - node options,
   - input payload metadata/data hash,
   - upload fingerprints.
4. Publish:

```text
node_started
```

5. If `previous_run_id` has the same cache key for this node:
   - copy previous output artifact files into the current run,
   - register copied artifacts,
   - publish `artifact_created` for each copied file,
   - publish `node_completed` with `data.cached = true`,
   - return reused `TypedPayload`s.

6. Otherwise, find the handler in `backend/nodes/dispatch.py`.
7. Call:

```python
await handler(ctx, workflow_node, input_payloads)
```

8. Handler returns:

```python
{
  "output_key": TypedPayload(...)
}
```

9. The adapter records each output in `run_registry.outputs`.
10. Each output is wrapped in `FoundryPayloadData` and sent to the corresponding Ryvencore output socket.
11. Publish:

```text
node_completed
```

### 8. What Node Handlers Receive And Send

Every handler has the same shape:

```python
async def handler(
  ctx: ExecutionContext,
  node: WorkflowNode,
  inputs: dict[str, TypedPayload],
) -> dict[str, TypedPayload]:
  ...
```

Receives:

- `ctx`: run id, artifact store, run registry, embedded uploads.
- `node`: node id, type, options.
- `inputs`: typed payloads produced by upstream nodes.

Sends:

- a mapping of output key to `TypedPayload`.
- artifacts through `ctx.write_*_artifact` or `copy_paths_as_artifacts`.
- SSE `artifact_created` events when artifacts are registered.
- structured errors by raising `BackendError`.

Examples:

- `LigandInput`
  - Receives no graph input; reads embedded/stored uploads from `ctx.uploads` or upload ids in `node.options.file`.
  - Sends `Ligand` or `Batch Ligand` payload.
  - Stores normalized ligand PDB artifacts.

- `ProteinInput`
  - Receives uploaded PDB content.
  - Sends `Batch Protein`.
  - Stores PDB artifacts.

- `SequenceInput`
  - Receives uploaded FASTA.
  - Sends `Batch Sequence`.
  - Stores FASTA artifact.

- Selector/manual nodes
  - Receive upstream structure payloads.
  - Send `input_required` event to frontend.
  - Wait for `POST /api/runs/{run_id}/input`.
  - Validate user selection against current PDB inputs.
  - Send list payloads such as `List of Atoms`, `List of Residues`, or `Residues Atoms List`.

- Generation/folding nodes
  - Receive structure, ligand, sequence, selector, and option payloads.
  - Call wrappers in `backend/foundry_tools/`.
  - External tool stdout/stderr is streamed as SSE `stdout` and `stderr`.
  - Tool outputs are converted/standardized when needed.
  - Send batch structure and/or score payloads.

- Filters
  - Receive structure batches and optional scores.
  - Validate score/structure length alignment.
  - Filter structures and scores together.
  - Send filtered structure payloads and optional filtered score payloads.

- Save nodes
  - Receive final payloads.
  - Materialize output files under `backend/runs/{run_id}/saves/`.
  - Send ZIP artifacts for frontend download.

### 9. Manual Input Round Trip

When a manual node needs frontend input:

Backend sends SSE:

```json
{
  "event": "input_required",
  "run_id": "run_...",
  "node_id": "selector-node",
  "node_type": "AtomSelector",
  "data": {
    "fields": ["atoms"],
    "payloads": {
      "ligand": {
        "type_name": "Ligand",
        "item_count": 1,
        "artifact_ids": ["artifact_..."],
        "paths": ["nodes/.../ligand.pdb"],
        "metadata": {}
      }
    },
    "defaults": { "atoms": "" },
    "choices": {}
  }
}
```

Frontend submits:

```text
POST /api/runs/{run_id}/input
```

```json
{
  "node_id": "selector-node",
  "values": { "atoms": "C1,O2,N1" }
}
```

Backend:

1. Finds the pending future for that node.
2. Resolves it with submitted values.
3. Publishes `node_progress` with message `User input received.`
4. The node handler resumes and returns its output payload.

### 10. Artifact Storage

Every run gets:

```text
backend/runs/{run_id}/
```

Every node writes under:

```text
backend/runs/{run_id}/nodes/{node_id}_{node_type}/
```

Artifacts are registered as:

```json
{
  "artifact_id": "artifact_...",
  "run_id": "run_...",
  "node_id": "node-id",
  "node_type": "RosettaFold3",
  "payload_type": "Batch Protein (With Ligand)",
  "media_type": "chemical/x-pdb",
  "path": "nodes/node_Type/file.pdb",
  "byte_size": 12345,
  "item_count": 1,
  "metadata": {}
}
```

The frontend can fetch:

- all artifacts: `GET /api/runs/{run_id}/artifacts`
- one artifact: `GET /api/artifacts/{artifact_id}`
- output list: `GET /api/runs/{run_id}/outputs`
- a single output download: `GET /api/runs/{run_id}/outputs/{node_id}/{output_key}/download`
- saved output ZIPs: `GET /api/runs/{run_id}/saves`
- full run ZIP: `GET /api/runs/{run_id}/archive`

### 11. Status Polling

Endpoint:

```text
GET /api/runs/{run_id}
```

Sends `RunStatus`:

```json
{
  "run_id": "run_...",
  "state": "running",
  "current_node_id": "node-id",
  "current_node_type": "RosettaFold3",
  "completed_nodes": 4,
  "total_nodes": 10,
  "progress_percent": 40,
  "recent_output": ["stdout: ...", "stderr: ..."],
  "warnings": [],
  "errors": [],
  "pending_inputs": []
}
```

The frontend uses this for progress, current node, recent logs, errors, and restoring pending manual inputs after reconnect/refresh.

### 12. Stop Flow

Endpoint:

```text
POST /api/runs/{run_id}/stop
```

Backend actions:

1. Marks `cancel_requested`.
2. Cancels pending manual-input futures.
3. If queued, immediately marks stopped.
4. Running node wrappers and the Ryvencore adapter check cancellation.
5. Subprocess wrappers terminate active process groups.
6. Publishes:

```text
stopped
```

The frontend can still request the run archive for whatever artifacts were created before stopping.

### 13. Error Flow

Handlers and validators raise or return `StructuredError` objects.

Shape:

```json
{
  "run_id": "run_...",
  "node_id": "node-id",
  "node_type": "FilterAtomsChirality",
  "interface_key": null,
  "option_key": "chiralityTargets",
  "code": "INVALID_ATOM_CHIRALITY_SELECTION",
  "message": "Selected atom(s) have no assigned R/S chirality: C1.",
  "details": {},
  "recoverable": false,
  "log_artifact_id": null
}
```

Runtime behavior:

1. `BackendError` is caught by `runtime.runner.run_workflow`.
2. `run_registry.add_error` stores the error.
3. Run state becomes `failed`.
4. SSE `error` is sent with the structured error in `data.error`.

### 14. Cache Flow

If a run belongs to a session and the previous session run exists:

1. `/api/runs` injects `previous_run_id`.
2. Each node computes a cache key.
3. If previous run has the same cache key for that node:
   - previous output files are copied into the new run folder,
   - artifacts are re-registered for the current run,
   - output payloads are updated to current artifact ids/paths,
   - `node_completed` is sent with `data.cached = true`.

The frontend displays cached nodes using this event field.

## End-To-End Summary

```text
Frontend
  POST /api/workflows/validate
    -> Backend validates WorkflowGraph
    <- valid/errors

Frontend
  POST /api/runs
    -> Backend validates graph and input files
    -> Creates run directory and RunRecord
    -> Enqueues QueuedRun
    <- accepted/run_id

Frontend
  GET /api/runs/{run_id}/events
    <- queued/started/node events/stdout/stderr/artifacts/errors/completed

Worker
  QueuedRun
    -> run_workflow
    -> execute_ryvencore_workflow
    -> Ryvencore Flow
    -> FoundryRyvencoreNode.update_event
    -> backend/nodes handler
    -> artifact_store + run_registry
    -> TypedPayload output to next node

Frontend
  GET /api/runs/{run_id}/outputs
  GET /api/runs/{run_id}/artifacts
  GET /api/artifacts/{artifact_id}
  GET /api/runs/{run_id}/archive
    <- files and metadata
```

