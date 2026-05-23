from __future__ import annotations

import json
from pathlib import Path

from backend.artifacts.store import ArtifactStore
from backend.foundry_tools.common import checkpoint_path, collect_files, executable
from backend.runtime.registry import RunRegistry
from backend.runtime.subprocesses import run_command_streaming
from backend.schemas.errors import BackendError, make_error


async def run_rf3_fold(
    *,
    run_id: str,
    node_id: str,
    node_type: str,
    work_dir: Path,
    fasta_path: Path,
    ligand_path: Path | None,
    early_stopping_plddt_threshold: float,
    diffusion_batch_size: int,
    num_steps: int,
    seed: int,
    registry: RunRegistry,
    store: ArtifactStore,
) -> tuple[list[Path], list[Path]]:
    out_dir = work_dir / "rf3_outputs"
    input_json = work_dir / "rf3_batch_input.json"
    ckpt_path = checkpoint_path("FOUNDRYUI_RF3_CKPT", "models/rf3_foundry_01_24_latest_remapped.ckpt")
    if not ckpt_path.exists():
        raise BackendError(
            make_error(
                "MISSING_RF3_CHECKPOINT",
                "RosettaFold3 checkpoint file was not found.",
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
                details={"checkpoint_path": str(ckpt_path), "env_var": "FOUNDRYUI_RF3_CKPT"},
            )
        )
    payload = {"sequences": str(fasta_path), "seed": seed}
    if ligand_path is not None:
        payload["ligand"] = str(ligand_path)
    input_json.write_text(json.dumps(payload, indent=2))
    command = [
        executable("FOUNDRYUI_RF3_BIN", "rf3"),
        "fold",
        f"inputs={input_json}",
        f"out_dir={out_dir}",
        f"ckpt_path={ckpt_path}",
        f"early_stopping_plddt_threshold={early_stopping_plddt_threshold}",
        f"diffusion_batch_size={diffusion_batch_size}",
        f"num_steps={num_steps}",
        f"seed={seed}",
    ]
    await run_command_streaming(command=command, cwd=work_dir, run_id=run_id, node_id=node_id, node_type=node_type, registry=registry, store=store)
    structures = collect_files(out_dir, (".pdb",))
    scores = collect_files(out_dir, (".json", ".csv"))
    return structures, scores
