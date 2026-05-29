from pathlib import Path
import zipfile

from backend.nodes.registry import FoundryNode


class SaveNode(FoundryNode):
    category = "Save"
    terminal = True

    @staticmethod
    def safe_folder(value: str) -> Path:
        parts = [part for part in Path(value or "outputs").parts if part not in {"", ".", ".."}]
        return Path(*parts) if parts else Path("outputs")

    @staticmethod
    async def zip_saved_folder(ctx, node, target_dir: Path, filename: str, payload_type: str, item_count: int) -> None:
        archive_path = target_dir / filename
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(target_dir.iterdir()):
                if path.is_file() and path != archive_path:
                    archive.write(path, path.name)
        artifact = ctx.store.register_file(
            run_id=ctx.run_id,
            path=archive_path,
            payload_type=payload_type,
            node_id=node.id,
            node_type=node.type,
            media_type="application/zip",
            item_count=item_count,
        )
        await ctx.artifact_created(artifact)
