from backend.bio.ligand import ligand_matches_smiles_chirality
from backend.bio.pdb import split_pdb_complex
from backend.nodes.common import node_dir, option, payload_from_artifacts, read_payload_files, scores_to_rows
from backend.nodes.filter.base import FilterNode
from backend.schemas.errors import BackendError, make_error
from backend.workflow.catalog import OptionSpec as O
from backend.workflow.catalog import PortSpec as P


class FilterChirality(FilterNode):
    type_name = "FilterChirality"
    title = "Filter Chirality"
    description = "Keep complexes whose ligand chirality matches a standard SMILES."
    inputs = (P("complexes", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"), P("score", "Score", optional=True, label="Score"))
    options = (O("smiles", "textarea", "", required=True, label="Standard SMILES"),)
    outputs = (P("complexes", "Batch Protein (With Ligand)", label="Batch Protein (With Ligand)"), P("score", "Score", label="Score"))
    catalog_order = 190

    @classmethod
    async def execute(cls, ctx, node, inputs):
        complexes = inputs["complexes"]
        scores = inputs.get("score")
        if scores is not None:
            cls.ensure_score_alignment(ctx, node, complexes, scores, ["complexes", "score"])
        contents = read_payload_files(ctx, complexes)
        smiles = cls.chirality_smiles(ctx, node)
        keep = []
        for index, content in enumerate(contents):
            _, complex_ligand = split_pdb_complex(content)
            try:
                matches = ligand_matches_smiles_chirality(complex_ligand, smiles)
            except ValueError as exc:
                raise BackendError(make_error("INVALID_CHIRALITY_SMILES", str(exc), run_id=ctx.run_id, node_id=node.id, node_type=node.type, option_key="smiles")) from exc
            if matches:
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

    @staticmethod
    def chirality_smiles(ctx, node) -> str:
        smiles = str(option(node, "smiles", "") or "").strip()
        if not smiles:
            raise BackendError(
                make_error(
                    "MISSING_CHIRALITY_SMILES",
                    "FilterChirality requires a standard SMILES option with stereochemistry.",
                    run_id=ctx.run_id,
                    node_id=node.id,
                    node_type=node.type,
                    option_key="smiles",
                )
            )
        return smiles
