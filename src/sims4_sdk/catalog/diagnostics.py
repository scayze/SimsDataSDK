"""Structured diagnostics for best-effort package extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..core.dbpf import ResourceKey
from ..export import Serializable

__all__ = ["ExtractionIssue"]


@dataclass(frozen=True)
class ExtractionIssue(Serializable):
    """One failed extraction step, with its source when available.

    ``recoverable`` describes whether the surrounding operation continued, not
    whether the skipped data can be recovered.  ``None`` means it is unknown.
    ``unsupported_format`` identifies a format only when positively known.
    """

    stage: str
    message: str
    exception_type: str
    package_path: Optional[str] = None
    resource_key: Optional[ResourceKey] = None
    tuning_id: Optional[int] = None
    recoverable: Optional[bool] = None
    unsupported_format: Optional[str] = None

    @classmethod
    def from_exception(
        cls, stage: str, exc: Exception, *, package_path: Optional[str] = None,
        resource_key: Optional[ResourceKey] = None, tuning_id: Optional[int] = None,
        recoverable: Optional[bool] = None, unsupported_format: Optional[str] = None,
    ) -> "ExtractionIssue":
        return cls(stage, str(exc), type(exc).__name__, package_path, resource_key,
                   tuning_id, recoverable, unsupported_format)
