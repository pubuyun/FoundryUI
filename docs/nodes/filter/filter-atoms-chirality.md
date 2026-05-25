# Filter Atoms Chirality

Manual filter that asks for ligand atom chirality targets and keeps complexes matching them.

Inputs:

- `Batch Protein (With Ligand)`: <span class="type complex">Batch Protein (With Ligand)</span>.
- `Score*`: optional <span class="type score">Score</span>.

Options:

- `Atom chirality targets`: entries such as `C1:R, C4:S`. The runtime viewer can help select atoms.

Output:

- Complexes and optional scores passing the selected chirality constraints.
