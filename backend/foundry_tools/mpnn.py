from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.artifacts.store import ArtifactStore
from backend.foundry_tools.common import checkpoint_path, collect_files, executable
from backend.runtime.registry import RunRegistry
from backend.runtime.subprocesses import run_command_streaming
from backend.schemas.errors import BackendError, make_error

AA_1_TO_3 = {
    "A": "ALA",
    "C": "CYS",
    "D": "ASP",
    "E": "GLU",
    "F": "PHE",
    "G": "GLY",
    "H": "HIS",
    "I": "ILE",
    "K": "LYS",
    "L": "LEU",
    "M": "MET",
    "N": "ASN",
    "P": "PRO",
    "Q": "GLN",
    "R": "ARG",
    "S": "SER",
    "T": "THR",
    "V": "VAL",
    "W": "TRP",
    "Y": "TYR",
}


async def run_mpnn_design(
    *,
    run_id: str,
    node_id: str,
    node_type: str,
    work_dir: Path,
    input_dir: Path,
    out_dir_name: str,
    model_type: str,
    checkpoint_env: str,
    checkpoint_default: str,
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
    out_dir = work_dir / out_dir_name
    inference_script = checkpoint_path("FOUNDRYUI_MPNN_INFERENCE", "foundry/models/mpnn/src/mpnn/inference.py")
    ckpt_path = checkpoint_path(checkpoint_env, checkpoint_default)
    if not inference_script.exists():
        raise BackendError(
            make_error(
                "MISSING_MPNN_INFERENCE_SCRIPT",
                "Foundry MPNN inference script was not found.",
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
                details={"inference_script": str(inference_script), "env_var": "FOUNDRYUI_MPNN_INFERENCE"},
            )
        )
    if not ckpt_path.exists():
        raise BackendError(
            make_error(
                "MISSING_MPNN_CHECKPOINT",
                "Foundry MPNN checkpoint file was not found.",
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
                details={"checkpoint_path": str(ckpt_path), "env_var": checkpoint_env},
            )
        )

    structures = collect_files(input_dir, (".pdb", ".cif", ".cif.gz"))
    if not structures:
        raise BackendError(
            make_error(
                "MISSING_MPNN_INPUT_STRUCTURES",
                "MPNN did not receive any PDB or CIF input structures.",
                run_id=run_id,
                node_id=node_id,
                node_type=node_type,
                details={"input_dir": str(input_dir)},
            )
        )

    for structure_path in structures:
        command = build_mpnn_command(
            inference_script=inference_script,
            checkpoint_path=ckpt_path,
            out_dir=out_dir,
            structure_path=structure_path,
            model_type=model_type,
            residue_role=residue_role,
            residues=residues,
            number_of_batches=number_of_batches,
            batch_size=batch_size,
            seed=seed,
            temperature=temperature,
            bias_aa=bias_aa,
            omit_aa=omit_aa,
        )
        await run_command_streaming(
            command=command,
            cwd=work_dir,
            run_id=run_id,
            node_id=node_id,
            node_type=node_type,
            registry=registry,
            store=store,
        )
    return collect_files(out_dir, (".fa", ".fasta"))


def build_mpnn_command(
    *,
    inference_script: Path,
    checkpoint_path: Path,
    out_dir: Path,
    structure_path: Path,
    model_type: str,
    residue_role: str,
    residues: list[str],
    number_of_batches: int,
    batch_size: int,
    seed: int,
    temperature: float,
    bias_aa: str,
    omit_aa: str,
) -> list[str]:
    command = [
        executable("FOUNDRYUI_MPNN_PYTHON", sys.executable),
        str(inference_script),
        "--model_type",
        model_type,
        "--checkpoint_path",
        str(checkpoint_path),
        "--is_legacy_weights",
        "True",
        "--structure_path",
        str(structure_path),
        "--out_directory",
        str(out_dir),
        "--batch_size",
        str(batch_size),
        "--number_of_batches",
        str(number_of_batches),
        "--seed",
        str(seed),
        "--temperature",
        str(temperature),
        "--write_fasta",
        "True",
        "--write_structures",
        "True",
    ]
    if residues:
        command.extend([_foundry_residue_role(residue_role), ",".join(residues)])
    bias = _bias_aa_to_json(bias_aa)
    if bias:
        command.extend(["--bias", bias])
    omit = _omit_aa_to_json(omit_aa)
    if omit:
        command.extend(["--omit", omit])
    return command


def _foundry_residue_role(residue_role: str) -> str:
    if residue_role == "redesigned_residues":
        return "--designed_residues"
    if residue_role == "designed_residues":
        return "--designed_residues"
    return "--fixed_residues"


def _bias_aa_to_json(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("{"):
        return value
    bias: dict[str, float] = {}
    for token in value.split(","):
        if not token.strip():
            continue
        aa, amount = token.split(":", 1)
        bias[_aa_name(aa.strip())] = float(amount)
    return json.dumps(bias)


def _omit_aa_to_json(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("["):
        return value
    tokens = [part.strip() for part in value.split(",") if part.strip()] if "," in value else list(value)
    return json.dumps([_aa_name(token) for token in tokens])


def _aa_name(value: str) -> str:
    upper = value.upper()
    if len(upper) == 1:
        return AA_1_TO_3[upper]
    return upper
