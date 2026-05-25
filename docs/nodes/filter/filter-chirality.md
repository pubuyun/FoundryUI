# Filter Chirality

Filters complexes by comparing the ligand in each complex to a standard SMILES.

Inputs:

- `Batch Protein (With Ligand)`: <span class="type complex">Batch Protein (With Ligand)</span>.
- `Score*`: optional <span class="type score">Score</span> to preserve alignment.

Options:

- `Standard SMILES`: canonical/isomeric SMILES used as chirality reference.

Output:

- Complexes that match the ligand chirality.
- Optional filtered score output.
