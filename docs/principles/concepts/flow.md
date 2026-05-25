# Flow

A run starts from load nodes and proceeds through connected nodes. Data movement is typed and artifact-backed.

For batch co-folding, parallel inputs are handled by index:

- Input 1 item 1 folds with input 2 item 1.
- Input 1 item 2 folds with input 2 item 2.
- A one-item batch can be broadcast across the longest batch.
- A single <span class="type ligand">Ligand</span> is reused across all folds.

If structures and scores are both present, their lengths must match. Filters preserve structure-score alignment.
