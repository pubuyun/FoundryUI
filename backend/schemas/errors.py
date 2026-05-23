from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StructuredError(BaseModel):
    run_id: str | None = None
    node_id: str | None = None
    node_type: str | None = None
    interface_key: str | None = None
    option_key: str | None = None
    code: str
    message: str
    details: dict[str, Any] = {}
    recoverable: bool = False
    log_artifact_id: str | None = None


class BackendError(Exception):
    def __init__(self, error: StructuredError):
        super().__init__(error.message)
        self.error = error


def make_error(
    code: str,
    message: str,
    *,
    run_id: str | None = None,
    node_id: str | None = None,
    node_type: str | None = None,
    interface_key: str | None = None,
    option_key: str | None = None,
    details: dict[str, Any] | None = None,
    recoverable: bool = False,
    log_artifact_id: str | None = None,
) -> StructuredError:
    return StructuredError(
        run_id=run_id,
        node_id=node_id,
        node_type=node_type,
        interface_key=interface_key,
        option_key=option_key,
        code=code,
        message=message,
        details=details or {},
        recoverable=recoverable,
        log_artifact_id=log_artifact_id,
    )
