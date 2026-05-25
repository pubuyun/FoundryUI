# Types

Types define which ports can connect and how payloads are interpreted.

<span class="type ligand">Ligand</span> is one standardized ligand PDB payload.

<span class="type batch-ligand">Batch Ligand</span> is a ligand collection. In RF3 co-folding, multiple connected ligand inputs are paired by index when they are batches; single ligands are reused for every fold.

<span class="type protein">Protein</span> and <span class="type batch-protein">Batch Protein</span> represent protein structures.

<span class="type complex">Batch Protein (With Ligand)</span> accepts protein-only or protein-ligand complex collections. It is useful for nodes that can operate on either.

<span class="type sequence">Batch Sequence</span> is a sequence collection, usually from FASTA or MPNN.

<span class="type score">Score</span> is a list of dictionaries aligned to a structure batch.

<span class="type residue">List of Residues</span>, <span class="type atom">List of Atoms</span>, and <span class="type residue-atoms">Residues Atoms List</span> carry selector results.
