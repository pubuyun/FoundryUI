# Merge

Merges two structure inputs into chain-separated structures.

Inputs:

- `Input A`: <span class="type complex">Batch Protein (With Ligand)</span>.
- `Input B`: <span class="type complex">Batch Protein (With Ligand)</span>.

Behavior:

- Single ligands or proteins can be applied across a batch.
- Batch inputs are merged by index when appropriate.

Output:

- `complexes`: merged <span class="type complex">Batch Protein (With Ligand)</span>.
