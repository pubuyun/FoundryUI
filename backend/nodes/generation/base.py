from backend.foundry_tools.rfd3 import run_rfd3_payload
from backend.nodes.registry import FoundryNode


class GenerationNode(FoundryNode):
    category = "Generation"

    @staticmethod
    def atom_map(payload) -> dict[str, str]:
        if payload is None:
            return {}
        data = payload.data or {}
        if isinstance(data, dict):
            return {str(key): str(value) for key, value in data.items()}
        return {}

    @staticmethod
    def residue_list(payload) -> list[str]:
        if payload is None:
            return []
        if isinstance(payload.data, list):
            return [str(item) for item in payload.data if str(item)]
        if isinstance(payload.data, str):
            return [item.strip() for item in payload.data.split(",") if item.strip()]
        return []

    @staticmethod
    def bool_option(value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in {"false", "0", "no", "off", ""}

    @staticmethod
    async def run_rfd3_payload(**kwargs):
        return await run_rfd3_payload(**kwargs)
