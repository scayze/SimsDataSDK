"""Structured diagnostics for best-effort package extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core.dbpf import ResourceKey
from ..export import Serializable

__all__ = ["ExtractionIssue"]


@dataclass(frozen=True)
class ExtractionIssue(Serializable):
    """One failed extraction step, with its source when available."""

    stage: str
    message: str
    exception_type: str
    package_path: Optional[str] = None
    resource_key: Optional[ResourceKey] = None
    tuning_id: Optional[int] = None

    @classmethod
    def from_exception(
        cls, stage: str, exc: Exception, *, package_path: Optional[str] = None,
        resource_key: Optional[ResourceKey] = None, tuning_id: Optional[int] = None,
    ) -> "ExtractionIssue":
        return cls(stage, str(exc), type(exc).__name__, package_path, resource_key, tuning_id)
