# Nodes

Nodes are the units of work in FoundryUI.

Common node groups:

- Load nodes turn uploaded files into typed payloads.
- Selector nodes pause execution and ask the user to choose residues, atoms, chains, or chirality targets from upstream structures.
- Generation and MPNN nodes call Foundry command-line tools.
- Folding nodes call RF3.
- Filter and logic nodes keep or combine aligned batches.
- Save nodes materialize selected artifacts into run save folders.

Manual nodes are marked in the canvas. Once a manual node has been answered for unchanged inputs, its cached output can be reused.
