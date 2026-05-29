import asyncio
import re

from backend.bio.ligand import ligand_has_atom_chirality_targets, validate_ligand_atom_chirality_targets
from backend.bio.pdb import split_pdb_complex
from backend.nodes.common import node_dir, option, payload_from_artifacts, read_payload_files, scores_to_rows
from backend.nodes.filter.base import FilterNode
from backend.schemas.errors import BackendError, make_error
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class FilterAtomsChirality(FilterNode):
    type_name = "FilterAtomsChirality"
    title = "Filter Atoms Chirality"
    description = "Pause at runtime and keep complexes whose selected ligand atoms match R/S chirality."
    inputs = (P("complexes", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"), P("score", "Score", optional=True, label="Score"))
    options = (O("chiralityTargets", "textarea", "", label="Select manually when run reaches this node"), O("viewer", "viewer", "Open", label="3D Selector", viewer_mode="atom"))
    outputs = (P("complexes", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"), P("score", "Score", label="Score"))
    ui = {"manual": True, "viewerMode": "atom", "selectorFields": {"atom": "chiralityTargets"}, "structureSource": "runtimePayloadsOrConnectedSource", "chiralityTargets": True, "blinkWhenPending": True}
    catalog_order = 200

    @classmethod
    async def execute(cls, ctx, node, inputs):
        complexes = inputs["complexes"]
        scores = inputs.get("score")
        if scores is not None:
            cls.ensure_score_alignment(ctx, node, complexes, scores, ["complexes", "score"])
        contents = read_payload_files(ctx, complexes)
        targets = await cls.runtime_atom_chirality_targets(ctx, node, complexes)
        if contents:
            _, first_ligand = split_pdb_complex(contents[0])
            try:
                validate_ligand_atom_chirality_targets(first_ligand, targets)
            except ValueError as exc:
                raise BackendError(
                    make_error(
                        "INVALID_ATOM_CHIRALITY_SELECTION",
                        str(exc),
                        run_id=ctx.run_id,
                        node_id=node.id,
                        node_type=node.type,
                        option_key="chiralityTargets",
                        details={"targets": [{"atom": atom, "chirality": chirality} for atom, chirality in targets]},
                    )
                ) from exc
        keep = []
        for index, content in enumerate(contents):
            _, complex_ligand = split_pdb_complex(content)
            if ligand_has_atom_chirality_targets(complex_ligand, targets):
                keep.append(index)
        out_dir = node_dir(ctx, node)
        artifacts = []
        kept_contents = []
        for new_index, old_index in enumerate(keep, start=1):
            content = contents[old_index]
            kept_contents.append(content)
            artifacts.append(await ctx.write_text_artifact(node, out_dir / f"complex_{new_index:04d}.pdb", content, "Batch Protein (With Ligand)", "chemical/x-pdb"))
        result = {"complexes": payload_from_artifacts("Batch Protein (With Ligand)", artifacts, data=kept_contents)}
        if scores is not None:
            kept_scores = [scores.data[index] for index in keep]
            json_artifact = await ctx.write_json_artifact(node, out_dir / "scores.json", kept_scores, "Score", item_count=len(kept_scores))
            csv_artifact = await ctx.write_csv_artifact(node, out_dir / "scores.csv", scores_to_rows(kept_scores), "Score")
            result["score"] = payload_from_artifacts("Score", [json_artifact, csv_artifact], data=kept_scores, item_count=len(kept_scores))
        return result

    @classmethod
    async def runtime_atom_chirality_targets(cls, ctx, node, complexes) -> list[tuple[str, str]]:
        first_ligand_artifact = None
        if complexes.paths:
            first_complex = ctx.store.absolute(ctx.run_id, complexes.paths[0]).read_text()
            _, first_ligand = split_pdb_complex(first_complex)
            first_ligand_artifact = await ctx.write_text_artifact(node, node_dir(ctx, node) / "first_ligand_for_chirality.pdb", first_ligand, "Ligand", "chemical/x-pdb")
        payloads = {}
        if first_ligand_artifact is not None:
            payloads["ligand"] = {"type_name": "Ligand", "item_count": 1, "artifact_ids": [first_ligand_artifact.artifact_id], "paths": [first_ligand_artifact.path], "metadata": {"source": "first_complex"}}
        payloads["complexes"] = {"type_name": complexes.type_name, "item_count": complexes.item_count, "artifact_ids": complexes.artifact_ids[:1], "paths": complexes.paths[:1], "metadata": complexes.metadata}
        try:
            values = await ctx.registry.request_node_input(ctx.run_id, node.id, node.type, ["chiralityTargets"], payloads, {"chiralityTargets": option(node, "chiralityTargets", "")})
        except asyncio.CancelledError as exc:
            raise BackendError(make_error("RUN_CANCELLED", "Run was stopped while waiting for chirality input.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, recoverable=True)) from exc
        targets = cls.atom_chirality_targets(ctx, node, values.get("chiralityTargets", option(node, "chiralityTargets", "")))
        if not targets:
            raise BackendError(make_error("MISSING_ATOM_CHIRALITY_TARGETS", "FilterAtomsChirality requires at least one atom/chirality target.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="chiralityTargets"))
        return targets

    @classmethod
    def atom_chirality_targets(cls, ctx, node, raw) -> list[tuple[str, str]]:
        if raw in (None, ""):
            return []
        if isinstance(raw, list):
            return [cls.target_from_item(ctx, node, item) for item in raw]
        entries = [entry.strip() for entry in re.split(r"[,;\n]+", str(raw)) if entry.strip()]
        return [cls.target_from_text(ctx, node, entry) for entry in entries]

    @classmethod
    def target_from_item(cls, ctx, node, item) -> tuple[str, str]:
        if isinstance(item, dict):
            atom = str(item.get("atom") or item.get("atomName") or item.get("name") or "").strip()
            chirality = str(item.get("chirality") or item.get("cip") or "").strip().upper()
            return cls.validate_target(ctx, node, atom, chirality, item)
        if isinstance(item, (list, tuple)) and len(item) == 2:
            return cls.validate_target(ctx, node, str(item[0]).strip(), str(item[1]).strip().upper(), item)
        return cls.target_from_text(ctx, node, str(item))

    @classmethod
    def target_from_text(cls, ctx, node, text: str) -> tuple[str, str]:
        parts = [part for part in re.split(r"[:=\s]+", text.strip()) if part]
        if len(parts) != 2:
            raise BackendError(make_error("INVALID_ATOM_CHIRALITY_TARGET", "FilterAtomsChirality target entries must be atom/chirality pairs like C1:S.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="chiralityTargets", details={"entry": text}))
        return cls.validate_target(ctx, node, parts[0], parts[1].upper(), text)

    @staticmethod
    def validate_target(ctx, node, atom_name: str, chirality: str, source) -> tuple[str, str]:
        if not atom_name or chirality not in {"R", "S"}:
            raise BackendError(make_error("INVALID_ATOM_CHIRALITY_TARGET", "FilterAtomsChirality target entries must include an atom name and chirality R or S.", run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="chiralityTargets", details={"entry": source}))
        return atom_name, chirality
