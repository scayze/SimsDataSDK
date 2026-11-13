"""Reader for SimData resources (type ``0x545AC67A``).

SimData resources are binary ``DATA`` blobs.  They are the compiled companion
to tuning XML and are also used for client-side catalog data (names, icons,
descriptions).  This reader exposes the raw table and schema structure for domain extractors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from ..exceptions import Sims4SDKError
from .data_tables import DataTables
from .resource_types import SIMDATA_TYPE_ID

__all__ = ["SimData", "SimDataError"]


class SimDataError(Sims4SDKError, ValueError):
    """Raised when a SimData resource cannot be decoded."""


@dataclass
class SimData:
    """A parsed SimData resource."""

    tables: DataTables

    TYPE_ID = SIMDATA_TYPE_ID

    @classmethod
    def parse(cls, data: bytes) -> "SimData":
        if not data.startswith(b"DATA"):
            raise SimDataError(
                f"SimData resource does not start with DATA (got {data[:4]!r})"
            )
        return cls(tables=DataTables.parse(data))

    # ------------------------------------------------------------------
    # convenience accessors
    # ------------------------------------------------------------------
    @property
    def version(self) -> int:
        return self.tables.version

    def table(self, name: str) -> tuple[Any, list[Any]]:
        return self.tables.table(name)

    def table_names(self) -> list[str]:
        return self.tables.table_names()

    def iter_rows(self, name: str) -> Iterator[dict[str, Any]]:
        _, rows = self.table(name)
        yield from rows

    def describe(self) -> str:
        return self.tables.describe()

    def __repr__(self) -> str:
        return f"SimData(tables={len(self.tables.tables)})"
