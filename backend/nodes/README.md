# Backend Node Guide

This guide describes how to add or change backend nodes in FoundryUI.

The backend uses one Python class per node. A node class owns its catalog metadata, ports, options, UI hints, validation metadata, and execution logic. In the usual case, adding a node means adding one `.py` file under the correct category folder.

## Folder Layout

Put node files under `backend/nodes/<category>/`.

Examples:

```text
backend/nodes/filter/FilterByScore.py
backend/nodes/folding/RosettaFold.py
backend/nodes/input/ProteinInput.py
backend/nodes/selector/AtomSelector.py
backend/nodes/save/SaveSequences.py
```

Each category has a base class:

```text
backend/nodes/filter/base.py
backend/nodes/folding/base.py
backend/nodes/input/base.py
backend/nodes/selector/base.py
```

Use the most specific base class available. Shared helpers used by all nodes belong on `FoundryNode` in `backend/nodes/registry.py`. Helpers used only by one category belong in that category base class. Helpers used only by one node belong in that node class file.

## Discovery

Nodes are discovered automatically by `backend/nodes/registry.py`.

Discovery imports Python files in these packages:

```text
note, selector, filter, input, generation, mpnn, folding,
scoring, logic, utility, viewer, save
```

Files starting with `_` and files named `base.py` are skipped. The class is registered when it subclasses `FoundryNode` and defines a non-empty `type_name`.

## Minimal Node

```python
from backend.nodes.common import node_dir, payload_from_artifacts, read_payload_files
from backend.nodes.scoring.base import ScoringNode
from backend.workflow.catalog import PortSpec as P


class CountStructures(ScoringNode):
    type_name = "CountStructures"
    title = "Count Structures"
    description = "Emit one score row per input structure."
    inputs = (P("structures", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"),)
    outputs = (P("score", "Score", label="Score"),)
    catalog_order = 900

    @classmethod
    async def execute(cls, ctx, node, inputs):
        structures = inputs["structures"]
        rows = [{"index": index, "structure_count": structures.item_count} for index, _ in enumerate(read_payload_files(ctx, structures), start=1)]
        json_artifact = await ctx.write_json_artifact(node, node_dir(ctx, node) / "scores.json", rows, "Score", item_count=len(rows))
        csv_artifact = await ctx.write_csv_artifact(node, node_dir(ctx, node) / "scores.csv", rows, "Score")
        return {"score": payload_from_artifacts("Score", [json_artifact, csv_artifact], data=rows, item_count=len(rows))}
```

## Required Class Variables

Every node class must define:

- `type_name`: stable internal node type string. This must match frontend workflow node types.
- `title`: user-facing display name.
- `inputs`: tuple of input `PortSpec` values. Use `()` for no inputs.
- `outputs`: tuple of output `PortSpec` values. Use `()` for terminal/no-output nodes.
- `execute`: async class method that runs the node and returns output payloads.

Strongly recommended:

- `description`: one sentence for the frontend catalog.
- `category`: inherited from the category base class.
- `options`: tuple of `OptionSpec` values. Use `()` when the node has no options.
- `catalog_order`: integer used for frontend ordering.

Optional:

- `aliases`: old node type names that should resolve to this class.
- `hidden`: hide compatibility/alias nodes from the frontend catalog.
- `terminal`: marks save/viewer nodes that do not feed downstream nodes.
- `ui`: frontend hints, especially for manual selector nodes.
- `upload_validation`: pre-run upload checks for input nodes.

## Ports

Import port specs as:

```python
from backend.workflow.catalog import PortSpec as P
```

Format:

```python
P(key, type_name, optional=False, label=None)
```

Examples:

```python
inputs = (
    P("structures", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"),
    P("score", "Score", optional=True, label="Score"),
)

outputs = (
    P("complexes", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"),
)
```

The `key` is how the handler reads and returns payloads. The `type_name` is the logical FoundryUI data type.

## Options

Import option specs as:

```python
from backend.workflow.catalog import OptionSpec as O
```

Format:

```python
O(key, kind, default, label=None, required=False, choices=(), min_value=None, max_value=None, accept=None, viewer_mode=None, frontend_default=None)
```

Common `kind` values:

- `text`
- `textarea`
- `select`
- `int`
- `float`
- `bool`
- `file`
- `viewer`

Read option values with:

```python
from backend.nodes.common import option

threshold = float(option(node, "threshold", 10))
mode = str(option(node, "mode", "Is largest top"))
```

Static validation checks required values, select choices, and numeric min/max. The handler must still validate runtime semantics.

## Execute Method

Every node must implement:

```python
@classmethod
async def execute(cls, ctx, node, inputs):
    ...
    return {"outputKey": typed_payload}
```

Parameters:

- `ctx`: `ExecutionContext`, run-scoped services and helpers.
- `node`: `WorkflowNode`, serialized workflow node and options.
- `inputs`: `dict[str, TypedPayload]`, keyed by declared input port key.

Rules:

- The method must be `async`.
- Return `dict[str, TypedPayload]`.
- Every returned key must match a declared output port.
- Do not return raw lists, dicts, strings, or absolute paths.
- Validate runtime assumptions before returning outputs.
- Raise `BackendError(make_error(...))` for user-facing failures.

## Execution Context

Important `ctx` fields and helpers:

- `ctx.run_id`: current run id.
- `ctx.store`: artifact store.
- `ctx.registry`: run registry, events, status, manual input, and output recording.
- `ctx.uploads`: embedded uploads indexed by workflow node id.
- `ctx.next_ligand_residue_name()`: generates `L:n` residue names for single ligand uploads.
- `ctx.write_text_artifact(...)`
- `ctx.write_json_artifact(...)`
- `ctx.write_csv_artifact(...)`
- `ctx.artifact_created(...)`

Use these helpers instead of writing unregistered output files.

## TypedPayload

`TypedPayload` is the only valid payload object passed between nodes.

Fields:

- `type_name`: logical type, such as `Batch Protein`, `Score`, or `List of Atoms`.
- `item_count`: number of logical items.
- `artifact_ids`: registered artifact ids.
- `paths`: run-relative artifact paths.
- `metadata`: machine-readable downstream context.
- `data`: small inline structured data.

Use `payload_from_artifacts(...)` for file-backed outputs:

```python
from backend.nodes.common import payload_from_artifacts

return {
    "batchProtein": payload_from_artifacts(
        "Batch Protein",
        artifacts,
        data=pdb_contents,
    )
}
```

Use direct `TypedPayload(...)` only when you need custom fields:

```python
from backend.schemas.payloads import TypedPayload

return {
    "atoms": TypedPayload(
        type_name="List of Atoms",
        item_count=len(atoms),
        data=atoms,
        metadata={"source": "manual_selection"},
    )
}
```

## Artifacts

Any file that should be inspected, downloaded, reused, or passed downstream must be registered as an artifact.

Recommended pattern:

```python
from backend.nodes.common import node_dir

artifact = await ctx.write_text_artifact(
    node,
    node_dir(ctx, node) / "protein_0001.pdb",
    pdb_text,
    "Batch Protein",
    "chemical/x-pdb",
)
```

Rules:

- Store node outputs under `node_dir(ctx, node)`.
- Payload `paths` must be run-relative, never absolute.
- Register generated/copied files before returning payloads that reference them.
- Keep artifact `payload_type` consistent with returned `TypedPayload.type_name`.

Project file conventions:

- Protein structures: `.pdb`
- Protein-ligand complexes: `.pdb`
- Ligands: `.pdb`
- Sequences: `.fasta`
- Scores: `.json` and `.csv`
- Atom/residue lists: `.json`

## Structured Errors

Use structured errors for expected user-facing failures:

```python
from backend.schemas.errors import BackendError, make_error

raise BackendError(
    make_error(
        "SCORE_LENGTH_MISMATCH",
        "Structure and score list lengths do not match.",
        run_id=ctx.run_id,
        node_id=node.id,
        node_type=node.type,
        interface_key="score",
        details={"expected_length": structures.item_count, "actual_length": scores.item_count},
        recoverable=False,
    )
)
```

Error rules:

- Use stable uppercase `code` values.
- Include `run_id`, `node_id`, and `node_type`.
- Include `interface_key` or `option_key` when relevant.
- Put machine-readable context in `details`.
- Prefer clear user-facing messages over raw exception strings.

## Shared Helpers

Available shared helper locations:

- `FoundryNode.ensure_score_alignment(...)`: shared structure/score length check.
- `SelectorNode`: runtime manual input, selector parsing, PDB selection validation.
- `GenerationNode`: RFDiffusion option and selector helpers.
- `MpnnNode`: MPNN FASTA output collection.
- `SaveNode`: safe save-folder and ZIP helpers.
- `ScoringNode`: score JSON/CSV artifact output.

Add new helpers where they belong:

- All nodes need it: `FoundryNode`.
- One category needs it: category `base.py`.
- One node needs it: the node class file.

## Manual Nodes

Manual nodes pause execution and request user input after upstream runtime payloads exist.

Class metadata must include:

```python
ui = {
    "manual": True,
    "viewerMode": "atom",
    "selectorFields": {"atom": "atoms"},
    "structureSource": "connectedSourceOutput",
    "blinkWhenPending": True,
}
```

Manual execution should:

- Pass runtime payload summaries to `ctx.registry.request_node_input(...)`.
- Include artifacts needed by frontend viewers.
- Validate returned selections against current runtime PDB/score data.
- Return normal `TypedPayload` outputs after input is received.
- Treat frontend selections as untrusted because refresh/session data can be stale.

See `backend/nodes/selector/base.py` and existing selector nodes for the standard pattern.

## Input Nodes

Input nodes should define `upload_validation`:

```python
from backend.nodes.registry import UploadValidation

upload_validation = UploadValidation(
    {"pdb"},
    "ProteinInput requires uploaded PDB content or upload file ids.",
    "MISSING_PROTEIN_FILE",
    "INVALID_PROTEIN_FILE",
)
```

Read uploads with:

```python
from backend.nodes.common import embedded_or_stored_uploads

uploads = embedded_or_stored_uploads(ctx, node)
```

Do not trust browser filesystem paths. Resolve uploads through the upload store or embedded workflow upload data.

## Batch Alignment

Preserve item alignment whenever payloads represent parallel batches.

Required behavior:

- If filtering structures, filter scores with the same indices.
- If structures and scores are both present, use `cls.ensure_score_alignment(...)`.
- If merging two batches, allow equal lengths or single-item broadcasting only when the node documents it.
- On mismatch, raise a structured error before writing downstream outputs.

Example:

```python
structures = inputs["structures"]
scores = inputs.get("score")

if scores is not None:
    cls.ensure_score_alignment(ctx, node, structures, scores, ["structures", "score"])
```

## Subprocess Nodes

For external tools such as RF3, RFDiffusion, LigandMPNN, and ProteinMPNN:

- Use wrappers under `backend/foundry_tools/`.
- Do not call long-running tools with bare blocking subprocess calls.
- Stream stdout/stderr through the event system via existing wrappers.
- Register output files as artifacts.
- Convert tool-specific structure formats into project-standard PDB before returning when needed.
- Check expected outputs exist and raise structured errors when they do not.
- Respect run cancellation by using existing subprocess helpers.

## Compatibility Wrappers

Some old module-level functions still exist in wrapper modules such as:

```text
backend/nodes/filters.py
backend/nodes/selectors.py
backend/nodes/utils.py
```

These are compatibility shims for tests and old imports. New node logic must not be placed there. Put implementation in the node class file.

## Pre-Commit Checklist

Before finishing a node change:

- The node is in the correct category folder.
- The class subclasses the correct base class.
- `type_name`, `title`, `inputs`, `outputs`, and `execute` are defined.
- `options`, `description`, and `catalog_order` are set where useful.
- Returned output keys match declared output ports.
- Returned payload types match declared output types.
- All generated files are registered as artifacts.
- Runtime selections are validated against runtime inputs.
- Structure/score alignment is preserved.
- Errors are structured and user-facing.
- Long-running commands stream logs and respect stop requests.
- Backend tests pass:

```bash
PYTHONPATH=/opt/FoundryUI .venv/bin/pytest backend/tests
```
