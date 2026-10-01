# Protein Binder

## Overview

This preset designs a new protein binder against a selected surface on a target protein. It uses interactive hotspot selection, RFDiffusion3 binder generation, sequence extraction, RosettaFold3 co-folding, score filtering, and structure review.

[image of the complete Protein Binder preset in FoundryUI]

Load `proteinbinder.fuiworkflow` from the preset menu. The included target and residue selections are examples and must be replaced for a new target.

## Workflow

### 1. Load and inspect the target

The **Protein Input** node loads the target PDB. The same structure is sent to the selector nodes, the generation node, and a chain-processing branch used later for co-folding.

To try the workflow, download [6EXS.pdb](https://gitlab.igem.org/2026/software/greatbay-scie/foundryui/-/raw/main/example_inputs/6EXS.pdb) and upload it in the **Protein Input** node. Inspect its chain identifiers and residue numbering before making selections. The preset refers to chain `A`; a target with different chain names requires corresponding updates.

### 2. Define the binding site

The **Residue Selector** identifies candidate hotspot residues. The preset lists `A25`, `A132`, and `A376`. The **Residue Atom Selector** then narrows the selection to specific atoms and initially maps residue `A376` to atoms `NH1,NH2`.

[image of hotspot residues and atoms highlighted on the target protein]

These values describe the template target only. For a new project, select solvent-accessible residues that represent the intended interface and atoms capable of the desired contacts.

### 3. Generate binder candidates

The target structure and hotspot map enter **RFDiffusion3 Protein Binder**. The preset requests one batch with a diffusion batch size of five. Its contig is `100-300,/0,A370-380`, which combines a generated segment with a region from the example target.

The contig and hotspot selections must agree with the uploaded target. Review the upstream RFDiffusion3 syntax before changing them; an incorrect chain or residue range can invalidate the design objective.

### 4. Prepare co-folding inputs

Two **Chain Filter** branches separate the generated binder and target chains. Each filtered structure passes through **Protein To Sequence**, producing one sequence input for the binder and another for the target.

Both sequence streams connect to **RosettaFold3** in `Co-folding` mode. This asks RF3 to predict the binder–target complex rather than folding each sequence independently.

[illustration of target and generated binder sequences entering RosettaFold3 co-folding]

### 5. Rank and inspect

RF3 produces predicted complexes and aligned score records. **Filter By Score** keeps the five highest `ranking_score` candidates. The filtered structures go to **PDB Viewer**, while **Save Proteins with Scores** packages the structures and their scores in `outputs`.

Inspect whether the binder contacts the selected surface, whether the interface is plausible, and whether confidence is concentrated at the interface rather than only within individual chains.

## Before running

- Replace the template PDB with the intended target.
- Update chain filters, residue numbers, hotspot atoms, and the contig together.
- Confirm that both target and binder sequence branches reach RF3.
- Start with modest batch sizes, then expand sampling after a successful test run.
- Use structural scores to prioritize candidates for further computational and experimental validation.

## Project resources

The [complete FoundryUI documentation](https://foundryui-dd6bba.igem.wiki/) covers all nodes, concepts, installation routes, and workflows. Source code and preset files are available in the [FoundryUI GitLab repository](https://gitlab.igem.org/2026/software/greatbay-scie/foundryui/-/blob/main/).
