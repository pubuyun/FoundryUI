from __future__ import annotations

from pathlib import Path

from backend.artifacts.store import ArtifactStore
from backend.foundry_tools.common import collect_files, executable
from backend.runtime.registry import RunRegistry
from backend.runtime.subprocesses import run_command_streaming


async def run_ligand_mpnn(
    *,
    run_id: str,
    node_id: str,
    node_type: str,
    work_dir: Path,
    input_dir: Path,
    residue_role: str,
    residues: list[str],
    number_of_batches: int,
    batch_size: int,
    seed: int,
    temperature: float,
    bias_aa: str,
    omit_aa: str,
    registry: RunRegistry,
    store: ArtifactStore,
) -> list[Path]:
    out_dir = work_dir / "ligand_mpnn_outputs"
    command = [
        executable("FOUNDRYUI_LIGAND_MPNN_BIN", "ligandmpnn"),
        f"--input_dir={input_dir}",
        f"--out_dir={out_dir}",
        f"--{residue_role}={','.join(residues)}",
        f"--number_of_batches={number_of_batches}",
        f"--batch_size={batch_size}",
        f"--seed={seed}",
        f"--temperature={temperature}",
    ]
    if bias_aa:
        command.append(f"--bias_AA={bias_aa}")
    if omit_aa:
        command.append(f"--omit_AA={omit_aa}")
    await run_command_streaming(command=command, cwd=work_dir, run_id=run_id, node_id=node_id, node_type=node_type, registry=registry, store=store)
    return collect_files(out_dir, (".fa", ".fasta"))
