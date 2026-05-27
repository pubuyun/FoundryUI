# Ligand Input

<div class="node-card">
Creates <span class="type ligand">Ligand</span> for one uploaded PDB or <span class="type batch-ligand">Batch Ligand</span> for multiple uploaded PDB files.
</div>

> [!options]
- `Upload File`: one or more `.pdb` files.
- `Open`: shows the uploaded ligand in the viewer.

Behavior:

- Single ligand uploads are standardized, have occupancy set to `1.00`, and are renamed to a run-unique residue name such as `L:1`.
- Batch ligand uploads are standardized but are not residue-renamed.

> [!output]
- `ligand`: <span class="type ligand">Ligand</span> or <span class="type batch-ligand">Batch Ligand</span>.
