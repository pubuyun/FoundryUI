# RFDiffusion3 Enzyme

Runs enzyme-style RFdiffusion from a protein-ligand theozyme.

Inputs:

- `Protein with Ligand`: <span class="type complex">Batch Protein with Ligand</span>.
- `ligand residues`: <span class="type residue">List of Residues</span>.
- `unindex residues`: <span class="type residue">List of Residues</span>.
- `select_fixed_atoms*`, `select_buried*`, `select_exposed*`: optional <span class="type residue-atoms">Residues Atoms List</span>.

Options:

- `dialect`: RFdiffusion dialect.
- `contig`: contig string.
- `is_non_loopy`: whether to request non-loopy designs.
- `n_batches`: number of designs.
- `diffusion_batch_size`: generation batch size.

Output:

- `complexes`: <span class="type complex">Batch Protein with Ligand</span>.
