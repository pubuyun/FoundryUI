# Protein MPNN

Runs ProteinMPNN sequence design for protein-only structures.

> [!input]
> - `Batch Protein`: <span class="type batch-protein">Batch Protein</span>.
> - `List of Residues*`: optional <span class="type residue">List of Residues</span>.

Options match Ligand MPNN:

- `Residue input role`, `number_of_batches`, `batch_size`, `seed`, `temperature`, `bias_AA`, and `omit_AA`.

> [!output]
> - `sequences`: <span class="type sequence">Batch Sequence</span>.
