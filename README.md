# FoundryUI

FoundryUI is a visual programming UI for Rosetta Foundry small molecule protein binder design workflows.

The initial environment is split into:

- `frontend/`: Nuxt 4, Vue 3, BaklavaJS, and 3Dmol.js.
- `backend/`: FastAPI, RyvenCore, Biopython, RDKit, and Rosetta Foundry.
- `foundry/`: Rosetta Foundry source checkout for source-level model runners such as MPNN inference.

## Prerequisites

- Node.js 22. Nuxt supports Node.js 20 or newer; this project starts on the installed Node 22 LTS line.
- Python 3.12 for Foundry and backend code. The setup script bootstraps a local interpreter with `uv` if it is not already available.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

The Nuxt development server defaults to `http://127.0.0.1:3000`.

## Backend

```bash
uv python install 3.12e
uv venv --clear --seed --python 3.12 .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.txt
python -m pip install "rc-foundry[all]"
export FOUNDRY_CHECKPOINT_DIRS="$PWD/models"
foundry install base-models --checkpoint-dir ./models
fastapi dev backend/main.py
```

The health check is exposed at `http://127.0.0.1:8000/health`.

## Setup Script

```bash
./setup.sh
```

The script creates a Python 3.12 `.venv` in the project root, installs backend Python requirements and `rc-foundry[all]`, clones Rosetta Foundry into `./foundry`, downloads Foundry base model checkpoints into `./models`, and runs `npm install` in `frontend/`. The Foundry checkout is kept because LigandMPNN inference is run from its MPNN source runner.

## Environment Notes

- Set `FOUNDRY_CHECKPOINT_DIRS="$PWD/models"` before Foundry inference commands that need the project-local checkpoints.
- Run LigandMPNN through Foundry's Python runner:

```bash
.venv/bin/python foundry/models/mpnn/src/mpnn/inference.py \
  --model_type ligand_mpnn \
  --checkpoint_path models/ligandmpnn_v_32_010_25.pt \
  --is_legacy_weights True \
  --structure_path path/to/input.cif \
  --out_directory path/to/mpnn_outputs \
  --batch_size 5 \
  --write_fasta True \
  --write_structures True
```

This is the Foundry equivalent of the legacy LigandMPNN `run.py` flow. The separate Dauparas `LigandMPNN` repository is not part of this environment.

- RDKit is declared as the PyPI package name `rdkit`.
- The workflow runners for RFdiffusion, LigandMPNN, ProteinMPNN, RosettaFold, and Rosetta Foundry are not added yet. They need their own model weights, executables, and compute policy once node execution work starts.
