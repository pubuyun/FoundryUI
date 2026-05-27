# RFDiffusion3 Protein Binder

Runs protein binder generation against an input protein.

> [!input]
> - `Protein`: <span class="type protein">Protein</span>.
> - `select_hotspots`: <span class="type residue-atoms">Residues Atoms List</span>.

> [!options]
> - `length`: generated binder length or range.
> - `contig`: RFdiffusion contig string.
> - `n_batches`: number of designs.
> - `diffusion_batch_size`: batch size for generation.

> [!output]
> - `batchProtein`: <span class="type batch-protein">Batch Protein</span>.
