# RFDiffusion3 SM Binder

Runs `rfd3 design` to design protein binders around a small molecule.

Inputs:

- `Ligand`: <span class="type ligand">Ligand</span>.
- `select_fixed_atoms*`: optional <span class="type atom">List of Atoms</span>.
- `select_buried*`: optional <span class="type atom">List of Atoms</span>.
- `select_exposed*`: optional <span class="type atom">List of Atoms</span>.

Options:

- `length`: binder length or range, for example `50-200`.
- `n_batches`: number of designs.
- `diffusion_batch_size`: RFdiffusion batch size.

Output:

- `complexes`: <span class="type complex">Batch Protein with Ligand</span>.
