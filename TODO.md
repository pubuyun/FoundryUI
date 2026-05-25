Rename Protein Atoms List to Residues Atoms List
Rename Protein Atom Selector Node to Resides Atom Selector.

Reference:
# RFdiffusion3 — Enzyme design examples
RFD3 contains several knobs and dials for enzyme design. 
- input: the pdb or cif file that contains the input theozyme
- ligand: any ligand res names that are to be included (comma separated)
- unindex: which residues should have their index be inferred by the model instead of prespecified
- length: the length range of the generated protein
- select_fixed_atoms: dictionary that indicated which atoms should be fixed (can use ALL, BKBN, or TIP for all atoms in the residue, backbone atoms only and tip atoms only)

If you would like to run the examples below, `enzyme_design.json`, located in this directory, contains the example code. You can run it via:
```
rfd3 design out_dir=inference_outputs/enzyme/0 \
ckpt_path=/path/to/rfd3_latest.ckpt \
inputs=./enzyme_design.json
```

Or, if you have cloned the repo rather than using `pip install`:
```
python path/to/foundry/models/rfd3/src/rfd3/run_inference.py \
out_dir=inference_outputs/enzyme/0 \
ckpt_path=/path/to/rfd3_latest.ckpt \
inputs=./enzyme_design.json 
```

An example script for running these examples in batches is also provided in `run_inf_tutorial.sh`.

The input files for the different examples are provided in `foundry/models/rfd3/docs/input_pdbs`.

```json
{
    "M0255_1mg5_unfixed": {
        "input": "../input_pdbs/M0255_1mg5.pdb", 
        "ligand": "NAI,ACT",
        "unindex": "A108,A139,A152,A156",
        "length": "180-200",
        "select_fixed_atoms": {
            "A108": "ND2,CG",
            "A139": "OG,CB,CA",
            "A152": "OH,CZ",
            "A156": "NZ,CE,CD",
            "ACT": "OXT",
            "NAI": ""
        },
        "select_buried": {
            "l:g": "O1,C8,O3,C4,C5,C23,C24,C25,C26,C27",
            "ACT": "OXT",
        },
        "select_exposed": {
            "l:g": "C2,C22,C19,C18,C17,C20,C16,C15,O21,O14,C13,C12",
            "NAI": "OXT",
        },
    }
}
```
# RFdiffusion3 — Protein binder design examples
RFD3 is a highly proficient protein binder designer. The following arguments have to be specified to RFD3 to make protein binders.
- input: the PDB or CIF file of the structure you want to bind
- contig: the length range of the binder to make (indicated as a range) and which residues from the target file to consider. 
- infer_ori_strategy: how RFD3 decides to place the origin of the generated protein binder with respect to the target. We find that using the "hotspots" strategy works best
- select_hotspots: which atoms on the target should be bound (dictionary of residues on the target and atoms in those residues)

In addition, we strongly recommend the following setting, which encourages the model to make more structured designs:
- is_non_loopy: true

We also recommend the following command-line overrides: `inference_sampler.step_scale=3` (defaults to 1.5) and
`inference_sampler.gamma_0=0.2` (defaults to 0.6). Increasing the `step_scale` and decreasing `gamma_0` yields lower-temperature
designs, which greatly increases PPI designability.

If you would like to run the examples below, `protein_binder_design.json`, located in this directory, contains the example code. You can run it via:
```
rfd3 design out_dir=inference_outputs/protein_binder/0 \
ckpt_path=/path/to/rfd3_latest.ckpt \
inputs=./protein_binder_design.json \
inference_sampler.step_scale=3 \
inference_sampler.gamma_0=0.2
```

Or, if you have cloned the repo rather than using `pip install`:
```
python path/to/foundry/models/rfd3/src/rfd3/run_inference.py \
out_dir=inference_outputs/protein_binder/0 \
ckpt_path=/path/to/rfd3_latest.ckpt \
inputs=./protein_binder_design.json \
inference_sampler.step_scale=3 \
inference_sampler.gamma_0=0.2
```

An example script for running these examples in batches is also provided in `run_inf_tutorial.sh`.

The input files for the different examples are provided in `foundry/models/rfd3/docs/input_pdbs`.

```json
{
    "insulinr": {
        "dialect": 2,
        "infer_ori_strategy": "hotspots",
        "input": "../input_pdbs/4zxb_cropped.pdb",
        "contig": "40-120,/0,E6-155",
        "select_hotspots": {
            "E64": "CD2,CZ",
            "E88": "CG,CZ",
            "E96": "CD1,CZ",
            },
        "is_non_loopy": true
    }
}
```

- Add Nodes
Node1: Protein Chain Selector
Stucking node
Input: Batch Protein
Option: 3d Selector, which allows the user to select a chain form the inputted proteins.
Output: Batch Protein, with only the selected chains.

Merge Node now can take the following types: Two Batch Protein With Ligand, Batch Protein, Batch Ligand, Ligand, Protein. 
The Merge Node should automatically merge two inputs. If one input is single, merge that with all structures in the other input.
Merged results should have the inputs structures in different chains.

Select Residues should not always in the format of "{chain}{number}". If the residue is not an standard amino acid, you should identify the real residue name like "LIG". Residue Atom Selector as well.

Node2: RFDiffusion Protein Binder
dialect should be an option
infer_ori_strategy should always be hotspots(not an option)
let user input contig as a string option
select_hotspots uses Residues Atoms List input
is_non_loopy is an option
Inputs: 
- Protein
- Residues Atoms List
Outputs: Batch Protein

Node3: Input Protein with Ligand
Same with Input protein, can input batch protein with ligand.
input: n/a
options: a 3d viewer button
output: Batch protein with ligand

Node4: RFDiffusion Enzyme
ligand should take an input of type List of Residue.
unindex should be an input of type List of Residue.
let user input length
select_fixed_atoms uses Residues Atoms List input
select_buried and select_exposed should take an Residues Atoms List input, but only containing ligand residues.
Inputs: 
- Protein with Ligand (single, take the first one if batch)
- List of Residue (ligand)
- List of Residue (unindex)
- Residues Atoms List
Outputs: Batch Protein with ligand

Make sure the inputs json are in correct format.