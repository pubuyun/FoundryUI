# Ligand Binder

## Overview

This preset designs proteins around a small molecule. It connects ligand preparation, atom selection, RFDiffusion3 backbone generation, LigandMPNN sequence design, RosettaFold3 structure prediction, chirality checking, score filtering, visualization, and export in one workflow.

[image of the complete Ligand Binder preset in FoundryUI]

The graph is available as `ligand-binder-denovo.fuiworkflow` in the preset menu. Its values are demonstration defaults, not universal design parameters.

## Workflow

### 1. Load the ligand

The **Ligand Input** node reads a ligand PDB. FoundryUI validates and standardizes the structure, then makes the same ligand available to generation and folding nodes.

To reproduce the example, download [Cys-Gly-(S)-3M3SH.pdb](https://gitlab.igem.org/2026/software/greatbay-scie/foundryui/-/raw/main/example_inputs/Cys-Gly-%28S%29-3M3SH.pdb) and upload it in the **Ligand Input** node. For another project, replace it with the intended molecule. Check its residue identity, bond representation, and stereochemistry before running the workflow.

### 2. Select interacting atoms

The **Atom Selector** opens the ligand in the 3D viewer. In this preset, the selected atoms are connected to both `select_fixed_atoms` and `select_buried` on **RFDiffusion3 SM Binder**. They therefore define atoms whose positions should remain constrained and be buried by the designed protein.

[image of ligand atoms selected in the 3D viewer]

The appropriate atoms depend on the intended binding mode. Select chemically meaningful interaction points rather than copying the example selection.

### 3. Generate binder backbones

**RFDiffusion3 SM Binder** generates protein–ligand complexes around the selected atoms. The preset uses:

| Parameter | Preset value | Meaning |
| --- | --- | --- |
| Length | `120-200` | Allowed binder-length range |
| Batches | `1` | Number of generation batches |
| Diffusion batch size | `2` | Designs generated per batch |

With these defaults, the node requests two candidate complexes. Increasing either batch setting explores more candidates but also increases GPU time and storage.

### 4. Design sequences

The generated complexes enter **LigandMPNN**, which proposes sequences while retaining ligand context. The preset fixes the selected residue positions and uses one batch of five sequences, seed `42`, and temperature `0.05`. A higher temperature generally increases sequence diversity.

### 5. Predict structures

The designed sequences and original ligand enter **RosettaFold3**. The preset uses 50 diffusion steps, seed `42`, and a diffusion batch size of one. RF3 returns predicted structures together with confidence metrics such as ranking score, pLDDT, pTM, and ipTM when available.

### 6. Filter and save

**Filter Atoms Chirality** removes complexes whose ligand stereochemistry does not match the selected targets. **Filter By Score** then keeps the top candidates by `ranking_score`; the preset threshold is 20, so all candidates may pass when the generated set is smaller.

The remaining structures are sent to **PDB Viewer** and **Save Proteins with Scores**. The save node packages each selected PDB with its aligned score record in the `outputs` folder.

[image of generated ligand-binding candidates being compared in the PDB Viewer]

## Before running

- Upload the intended ligand again after loading the preset.
- Review atom selections and chirality targets for that ligand.
- Choose generation counts that fit the available GPU memory and time.
- Treat confidence scores as computational screening evidence, not experimental proof of binding.
- Download both the run archive and `.fuiworkflow` file to preserve results and parameters.

## Project resources

The [complete FoundryUI documentation](https://foundryui-dd6bba.igem.wiki/) covers all nodes, concepts, installation routes, and workflows. Source code and preset files are available in the [FoundryUI GitLab repository](https://gitlab.igem.org/2026/software/greatbay-scie/foundryui/-/blob/main/).
