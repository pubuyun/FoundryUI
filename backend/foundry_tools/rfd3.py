from __future__ import annotations

import gzip
import json
from pathlib import Path

from Bio.PDB import MMCIFParser, PDBIO

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
    ligand_residue_name: str,
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
            "ligand": ligand_residue_name,
            "length": str(length),
            "select_fixed_atoms": {ligand_residue_name: ",".join(select_fixed_atoms)},
            "select_buried": {ligand_residue_name: ",".join(select_buried)},
            "select_exposed": {ligand_residue_name: ",".join(select_exposed)},
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
    return _standardize_rfd3_structures(out_dir, work_dir / "rfd3_pdb_outputs")


def _standardize_rfd3_structures(out_dir: Path, pdb_dir: Path) -> list[Path]:
    pdb_paths = collect_files(out_dir, (".pdb",))
    cif_gz_paths = collect_files(out_dir, (".cif.gz",))
    if not cif_gz_paths:
        return pdb_paths

    pdb_dir.mkdir(parents=True, exist_ok=True)
    parser = MMCIFParser(QUIET=True)
    converted_paths: list[Path] = []
    for cif_gz_path in cif_gz_paths:
        pdb_path = pdb_dir / f"{cif_gz_path.name.removesuffix('.cif.gz')}.pdb"
        with gzip.open(cif_gz_path, "rt") as handle:
            structure = parser.get_structure(cif_gz_path.stem, handle)
        writer = PDBIO()
        writer.set_structure(structure)
        writer.save(str(pdb_path))
        converted_paths.append(pdb_path)
    return [*pdb_paths, *converted_paths]
