from __future__ import annotations

from pathlib import Path

from backend.artifacts.store import ArtifactStore
from backend.foundry_tools.mpnn import run_mpnn_design
from backend.runtime.registry import RunRegistry


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
    return await run_mpnn_design(
        run_id=run_id,
        node_id=node_id,
        node_type=node_type,
        work_dir=work_dir,
        input_dir=input_dir,
        out_dir_name="ligand_mpnn_outputs",
        model_type="ligand_mpnn",
        checkpoint_env="FOUNDRYUI_LIGAND_MPNN_CKPT",
        checkpoint_default="models/ligandmpnn_v_32_010_25.pt",
        residue_role=residue_role,
        residues=residues,
        number_of_batches=number_of_batches,
        batch_size=batch_size,
        seed=seed,
        temperature=temperature,
        bias_aa=bias_aa,
        omit_aa=omit_aa,
        registry=registry,
        store=store,
    )
