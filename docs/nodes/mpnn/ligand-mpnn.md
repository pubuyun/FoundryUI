# Ligand MPNN

Runs LigandMPNN sequence design for protein-ligand complexes.

> [!input]
- `Batch Protein with Ligand`: <span class="type complex">Batch Protein with Ligand</span>.
- `List of Residues*`: optional <span class="type residue">List of Residues</span> for fixed or redesigned residues.

> [!options]
- `Residue input role`: `fixed_residues` or `redesigned_residues`.
- `number_of_batches`: number of MPNN batches.
- `batch_size`: designs per batch.
- `seed`: random seed.
- `temperature`: sampling temperature.
- `bias_AA`: global amino acid bias, for example `W:3.0,P:3.0,A:-3.0`.
- `omit_AA`: amino acids to omit.

> [!output]
- `sequences`: <span class="type sequence">Batch Sequence</span>.
