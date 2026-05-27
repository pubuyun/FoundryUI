# Merge

Merges two structure inputs into chain-separated structures.

> [!input]
> - `Input A`: <span class="type complex">Batch Protein (With Ligand)</span>.
> - `Input B`: <span class="type complex">Batch Protein (With Ligand)</span>.

Behavior:

- Single ligands or proteins can be applied across a batch.
- Batch inputs are merged by index when appropriate.

> [!output]
> - `complexes`: merged <span class="type complex">Batch Protein (With Ligand)</span>.
