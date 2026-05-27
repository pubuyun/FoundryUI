# RosettaFold3

Runs RF3 folding for sequence batches, optionally with ligand co-folding.

> [!input]
> - `Batch Sequence`: one or more connected <span class="type sequence">Batch Sequence</span> inputs.
> - `Batch Ligand*`: optional one or more connected <span class="type batch-ligand">Batch Ligand</span> or <span class="type ligand">Ligand</span> inputs.

> [!options]
> - `early_stopping_plddt_threshold`: RF3 early stopping threshold.
> - `diffusion_batch_size`: RF3 diffusion batch size.
> - `num_steps`: RF3 diffusion steps.
> - `seed`: random seed.
> - `Input mode`: `Concat inputs` or `Co-folding`.

Input modes:

- `Concat inputs`: old behavior. Each sequence is folded independently with the first ligand if provided.
- `Co-folding`: multiple connected sequence and ligand inputs are paired by index. One-item batch sequence inputs are reused across all folds. Single ligand inputs are reused for every fold. Batch ligand inputs must match the folding count.

> [!output]
> - `structures`: <span class="type complex">Batch Protein (With Ligand)</span>.
> - `score`: <span class="type score">Score</span>.
