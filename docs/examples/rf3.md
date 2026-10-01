# Folding Prediction

## Overview

This preset predicts structures from one or more protein sequences with RosettaFold3. An optional ligand can be included to evaluate protein folding in ligand context. Predicted structures, confidence scores, a 3D preview, and downloadable results are produced together.

[image of the complete Folding Prediction preset in FoundryUI]

Load `rf3.fuiworkflow` from the preset menu. This is the shortest supplied workflow and is useful for checking a new FoundryUI installation before running a larger design pipeline.

## Workflow

### 1. Load sequences

The **Sequence Input** node reads a FASTA file. Each record becomes an item in a `Batch Sequence` payload, allowing several designs to be processed in one run.

Two inputs are provided:

- [Download cgtase.fasta](https://gitlab.igem.org/2026/software/greatbay-scie/foundryui/-/raw/main/example_inputs/cgtase.fasta) for a single-sequence prediction.
- [Download binders-20.fasta](https://gitlab.igem.org/2026/software/greatbay-scie/foundryui/-/raw/main/example_inputs/binders-20.fasta) for a batch of 20 candidate binders.

Upload one of these files in **Sequence Input**. For a new dataset, use unique, descriptive FASTA identifiers and valid amino-acid sequences. The identifiers help connect RF3 output directories and score rows to the original designs.

### 2. Add an optional ligand

The **Ligand Input** accepts a ligand PDB and connects it to RF3. Leave this input unused for protein-only prediction. When a ligand is supplied, FoundryUI converts its representation for RF3 and retains ligand context in the predicted output.

[image of a sequence input and optional ligand connected to RosettaFold3]

### 3. Configure RosettaFold3

The preset uses the following starting values:

| Parameter | Preset value | Purpose |
| --- | --- | --- |
| Early-stopping pLDDT | `0.5` | Stops weak trajectories according to RF3 confidence |
| Diffusion batch size | `2` | Number of diffusion samples |
| Diffusion steps | `50` | Sampling depth and compute-time control |
| Seed | `42` | Reproducible random initialization |

Larger batch sizes and more steps require more GPU memory or time. Change one parameter at a time when comparing runs and record the checkpoint version with the results.

### 4. Review outputs

RF3 returns a structure batch and an aligned score payload. FoundryUI normalizes RF3 mmCIF output into PDB artifacts for downstream use and records available confidence values in JSON and CSV.

The structures are connected directly to **PDB Viewer** for visual inspection. **Save Proteins with Scores** packages each predicted structure with its score data in the `outputs` folder.

[image of a predicted fold in the PDB Viewer beside its confidence scores]

## Interpreting the result

Confidence metrics rank predictions but do not establish biological function. Examine overall fold quality, low-confidence regions, domain orientation, clashes, and—when a ligand is present—the predicted binding geometry. Compare important candidates with independent tools or experimental evidence.

For reproducibility, save the `.fuiworkflow` document and download the run archive. Together they preserve the graph, options, predicted structures, and score tables used in the analysis.

## Project resources

The [complete FoundryUI documentation](https://foundryui-dd6bba.igem.wiki/) covers all nodes, concepts, installation routes, and workflows. Source code and preset files are available in the [FoundryUI GitLab repository](https://gitlab.igem.org/2026/software/greatbay-scie/foundryui/-/blob/main/).
