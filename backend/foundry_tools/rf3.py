from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

from Bio.PDB import MMCIFParser, PDBIO

from backend.artifacts.store import ArtifactStore
from backend.foundry_tools.common import checkpoint_path, executable
from backend.runtime.registry import RunRegistry
from backend.runtime.subprocesses import run_command_streaming
from backend.schemas.errors import BackendError, make_error


async def run_rf3_fold(
    *,
    run_id: str,
    node_id: str,
    node_type: str,
    work_dir: Path,
    sequences: list[dict],
    ligand_smiles: str | None,
    early_stopping_plddt_threshold: float,
    diffusion_batch_size: int,
    num_steps: int,
    seed: int,
    registry: RunRegistry,
    store: ArtifactStore,
) -> tuple[list[Path], list[dict[str, Any]]]:
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
    payload = build_rf3_jobs(sequences, ligand_smiles)
    if not payload:
        raise BackendError(
            make_error(
                "NO_RF3_INPUT_SEQUENCES",
                "RosettaFold3 requires at least one sequence.",
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
            )
        )
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
    structures, scores = collect_rf3_results(out_dir, work_dir / "rf3_pdb_outputs")
    return structures, scores


def build_rf3_jobs(sequences: list[dict], ligand_smiles: str | None) -> list[dict]:
    jobs: list[dict] = []
    for index, item in enumerate(sequences, start=1):
        sequence = str(item.get("sequence") or "").strip()
        if not sequence:
            continue
        record_id = str(item.get("id") or f"sequence_{index:04d}")
        components = [{"seq": sequence, "chain_id": "A"}]
        if ligand_smiles:
            components.append({"smiles": ligand_smiles})
        jobs.append({"name": _safe_job_name(record_id, index), "components": components})
    return jobs


def _safe_job_name(record_id: str, index: int) -> str:
    safe = "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in record_id).strip("._-")
    return safe or f"sequence_{index:04d}"


def collect_rf3_results(out_dir: Path, pdb_dir: Path) -> tuple[list[Path], list[dict[str, Any]]]:
    structure_paths: list[Path] = []
    scores: list[dict[str, Any]] = []
    for result_dir in _rf3_result_dirs(out_dir):
        model_path = _rf3_model_file(result_dir)
        if model_path is None:
            continue
        pdb_path = _convert_rf3_model_to_pdb(model_path, pdb_dir)
        structure_paths.append(pdb_path)
        scores.append(_rf3_score(result_dir, model_path))
    return structure_paths, scores


def _rf3_result_dirs(out_dir: Path) -> list[Path]:
    if not out_dir.exists():
        return []
    if _rf3_model_file(out_dir) is not None:
        return [out_dir]
    return sorted(path for path in out_dir.iterdir() if path.is_dir() and _rf3_model_file(path) is not None)


def _rf3_model_file(result_dir: Path) -> Path | None:
    expected = result_dir / f"{result_dir.name}_model.cif"
    if expected.is_file():
        return expected
    expected_gz = result_dir / f"{result_dir.name}_model.cif.gz"
    if expected_gz.is_file():
        return expected_gz
    expected_pdb = result_dir / f"{result_dir.name}_model.pdb"
    if expected_pdb.is_file():
        return expected_pdb
    candidates = sorted(
        path
        for path in result_dir.iterdir()
        if path.is_file() and (path.name.endswith("_model.cif") or path.name.endswith("_model.cif.gz") or path.name.endswith("_model.pdb"))
    )
    return candidates[0] if candidates else None


def _convert_rf3_model_to_pdb(model_path: Path, pdb_dir: Path) -> Path:
    if model_path.suffix.lower() == ".pdb":
        return model_path
    pdb_dir.mkdir(parents=True, exist_ok=True)
    parser = MMCIFParser(QUIET=True)
    if model_path.name.endswith(".cif.gz"):
        pdb_name = f"{model_path.name.removesuffix('.cif.gz')}.pdb"
        with gzip.open(model_path, "rt") as handle:
            structure = parser.get_structure(model_path.stem, handle)
    else:
        pdb_name = f"{model_path.stem}.pdb"
        structure = parser.get_structure(model_path.stem, str(model_path))
    pdb_path = pdb_dir / pdb_name
    writer = PDBIO()
    writer.set_structure(structure)
    writer.save(str(pdb_path))
    return pdb_path


def _rf3_score(result_dir: Path, model_path: Path) -> dict[str, Any]:
    design_id = result_dir.name
    conf = _read_json(result_dir / f"{design_id}_summary_confidences.json")
    ranking_score = conf.get("ranking_score", 0.0)
    ptm = conf.get("ptm", 0.0)
    iptm = conf.get("iptm", 0.0)
    plddt_raw = conf.get("overall_plddt", 0.0)
    plddt = plddt_raw * 100 if isinstance(plddt_raw, int | float) and plddt_raw <= 1.0 else plddt_raw
    interface_pae = _interface_pae(conf)
    return {
        "design_id": design_id,
        "length": _sequence_length(conf, model_path),
        "ranking_score": round(float(ranking_score or 0.0), 4),
        "pTM": round(float(ptm or 0.0), 4),
        "ipTM": round(float(iptm or 0.0), 4),
        "pLDDT": round(float(plddt or 0.0), 2),
        "interface_PAE": round(interface_pae, 2) if interface_pae is not None else None,
        "has_clash": conf.get("has_clash", True),
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else {}


def _interface_pae(conf: dict[str, Any]) -> float | None:
    try:
        chain_pair_pae_min = conf.get("chain_pair_pae_min", [])
        value = chain_pair_pae_min[0][1]
        return float(value) if value is not None else None
    except Exception:
        return None


def _sequence_length(conf: dict[str, Any], model_path: Path) -> int | None:
    length = conf.get("length") or conf.get("seq_length") or conf.get("L")
    if length:
        return int(length)
    sequence = conf.get("sequence")
    if isinstance(sequence, str):
        return len(sequence)
    if isinstance(sequence, dict) and isinstance(sequence.get("A"), str):
        return len(sequence["A"])
    return _count_chain_a_ca(model_path)


def _count_chain_a_ca(model_path: Path) -> int | None:
    opener = gzip.open if model_path.name.endswith(".gz") else open
    try:
        with opener(model_path, "rt") as handle:
            count = sum(1 for line in handle if line.startswith("ATOM") and " CA " in line and " A " in line)
        return count or None
    except Exception:
        return None
