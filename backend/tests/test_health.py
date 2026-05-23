import asyncio

from backend.main import health


def test_health() -> None:
    assert asyncio.run(health()) == {"status": "ok"}
