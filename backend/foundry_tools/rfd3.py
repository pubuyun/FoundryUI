from __future__ import annotations

import json
from pathlib import Path

from backend.foundry_tools.common import checkpoint_path, collect_files, executable
from backend.runtime.registry import RunRegistry
from backend.runtime.subprocesses import run_command_streaming
from backend.artifacts.store import ArtifactStore
from backend.schemas.errors import BackendError, make_error


async def run_rfd3_design(
    *,
    run_id: str,
    node_id: str,
    node_type: str,
    work_dir: Path,
    ligand_path: Path,
    length: int | str,
    n_batches: int,
    diffusion_batch_size: int,
    select_fixed_atoms: list[str],
    select_buried: list[str],
    select_exposed: list[str],
    registry: RunRegistry,
    store: ArtifactStore,
) -> list[Path]:
    out_dir = work_dir / "rfd3_outputs"
    input_json = work_dir / "sm_binder_design.json"
    ckpt_path = checkpoint_path("FOUNDRYUI_RFD3_CKPT", "models/rfd3_foundry_2025_12_01_remapped.ckpt")
    if not ckpt_path.exists():
        raise BackendError(
            make_error( 
                "MISSING_RFD3_CHECKPOINT",
                "RFDiffusion3 checkpoint file was not found.",
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
                details={"checkpoint_path": str(ckpt_path), "env_var": "FOUNDRYUI_RFD3_CKPT"},
            )
        )
    payload = {
        "foundryui_design": {
            "input": str(ligand_path),
            "ligand": "LIG",
            "length": str(length),
            "select_fixed_atoms": {"LIG": ",".join(select_fixed_atoms)},
            "select_buried": {"LIG": ",".join(select_buried)},
            "select_exposed": {"LIG": ",".join(select_exposed)},
        }
    }
    input_json.write_text(json.dumps(payload, indent=2))
    command = [
        executable("FOUNDRYUI_RFD3_BIN", "rfd3"),
        "design",
        f"out_dir={out_dir}",
        f"inputs={input_json}",
        f"ckpt_path={ckpt_path}",
        f"n_batches={n_batches}",
        f"diffusion_batch_size={diffusion_batch_size}",
    ]
    await run_command_streaming(command=command, cwd=work_dir, run_id=run_id, node_id=node_id, node_type=node_type, registry=registry, store=store)
    return collect_files(out_dir, (".pdb",))
