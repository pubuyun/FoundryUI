# Installing FoundryUI

FoundryUI can run on a Linux workstation or server, from a prepared AutoDL image, or in Google Colab. A local installation offers persistent storage and full control; the hosted options provide a faster route for evaluation or teams without a dedicated GPU machine.

## Choose an installation route

- **Local Linux:** best for development, persistent projects, and control over model versions.
- **AutoDL:** best for a prepared cloud GPU environment.
- **Google Colab:** best for a quick trial, including RF3 on a free T4 runtime.

## Local Linux installation

### Linux requirements

Provide Git, `curl`, npm, and Node.js 20 or newer; Node.js 22 LTS is the reference version. GPU model nodes require an NVIDIA GPU and a compatible CUDA-enabled PyTorch installation. Nginx is needed only for the included production deployment.

Allow enough disk space for model checkpoints and run artifacts. Model weights may have separate access conditions or licences that should be checked before redistribution.

### Automatic setup

```bash
git clone https://github.com/pubuyun/FoundryUI.git
cd FoundryUI
chmod +x setup.sh
./setup.sh
```

The script installs a project-local Python 3.12 environment, backend dependencies, `rc-foundry[all]`, the Foundry source used by MPNN, base-model checkpoints, and frontend packages. It uses local `.python/`, `.venv/`, `models/`, and `foundry/` directories rather than modifying the system Python environment.

### Starting FoundryUI

Start the backend:

```bash
source .venv/bin/activate
export FOUNDRY_CHECKPOINT_DIRS="$PWD/models"
fastapi dev backend/main.py
```

In a second terminal, start the frontend:

```bash
cd frontend
npm run dev
```

Open `http://127.0.0.1:3000`. The backend health endpoint is `http://127.0.0.1:8000/health`.

[image of the FoundryUI workbench with the API status showing available]

### Production deployment

After running `setup.sh`, the repository's production script builds the frontend and configures the Uvicorn, Nuxt, and Nginx runner:

```bash
sudo ./install-foundryui.sh
./run-foundryui-service.sh
```

The default public address is `http://127.0.0.1:3000`. Paths and ports can be changed through the environment variables documented in the script.

In the current version, the production script's clone and environment-setup calls are disabled in `main`, so `setup.sh` must be run first.

## Hosted installations

### AutoDL image

The shared [FoundryUI AutoDL image](https://www.autodl.art/i/pubuyun/FoundryUI/FoundryUI) provides a preconfigured GPU environment. Create an instance with suitable GPU memory and persistent storage, then follow the image's launch instructions.

[image of the FoundryUI AutoDL image page and instance creation controls]

Record the image version, GPU type, workflow, and checkpoint versions used for each experiment.

### Google Colab and free T4 support

The [FoundryUI Colab notebook](https://colab.research.google.com/drive/1D6h8yXTDaWO5cN0eClfx7FMFXIZ_t4N3) is the quickest trial route. Choose a GPU runtime and execute its cells in order.

The notebook adapts RF3 to the memory constraints of the free-tier NVIDIA T4 GPU, making folding available without a dedicated workstation. Use conservative batch sizes. Colab sessions are temporary, so download workflow files and run archives before disconnecting.

[image of the Colab notebook running FoundryUI with a T4 GPU selected]

## Configuration and checks

### Checkpoints and CUDA

Checkpoint and executable locations can be overridden without changing a workflow. Common variables include `FOUNDRYUI_RFD3_CKPT`, `FOUNDRYUI_RF3_CKPT`, `FOUNDRYUI_RF3_BIN`, `FOUNDRYUI_MPNN_INFERENCE`, and the MPNN checkpoint variables.

If PyTorch reports a CUDA error, install a build compatible with the host driver. Check `nvidia-smi` and official PyTorch compatibility information before changing packages.

### Verification

```bash
curl http://127.0.0.1:8000/health
source .venv/bin/activate
python -m pytest backend/tests/test_health.py backend/tests/test_validation.py -q
cd frontend
npm run typecheck
```

The health endpoint should return `{"status":"ok"}`. Test a small workflow before committing significant GPU time; missing checkpoints or executables are reported as structured node errors.
