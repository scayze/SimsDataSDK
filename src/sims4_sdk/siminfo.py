"""Partial reader for SimInfo (``.siminfo`` / SIMO, type ``0x025ED6F4``).

SimInfo resources store the baked-in data of a pre-made or exported Sim.  The
full format is a proprietary serialization with several interleaved sections;
The reader extracts the parts needed for the static catalog:

* the resource's trait list (a byte count followed by 64-bit trait IDs),
* enough header information to locate that list.

The trait list is written immediately before the resource's CAS/appearance data.
Its position is encoded in the second uint32 of the header (the offset of the
*last* trait ID), so the list can be recovered by walking back in 8-byte strides
and validating the count byte and the IDs against the catalog.

Aspiration/career/skills baked into SimInfo are intentionally not parsed yet;
for pre-made Sims those values are usually supplied by the
``PremadeSimTemplate`` instead.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .exceptions import Sims4SDKError

__all__ = ["SimInfo", "SimInfoError"]


class SimInfoError(Sims4SDKError, ValueError):
    """Raised when a SimInfo resource cannot be read."""


@dataclass
class SimInfo:
    version: int
    last_trait_offset: int
    traits: list[int] = field(default_factory=list)
    raw: bytes = field(default=b"", repr=False)

    @classmethod
    def parse(
        cls,
        data: bytes,
        *,
        known_trait_ids: Optional[Iterable[int]] = None,
    ) -> "SimInfo":
        if len(data) < 8:
            raise SimInfoError(f"SimInfo is too small ({len(data)} bytes)")

        version, last_trait_offset = struct.unpack_from("<II", data, 0)
        known = set(known_trait_ids) if known_trait_ids is not None else None

        traits: list[int] = []
        if 0 < last_trait_offset + 8 <= len(data):
            traits = _find_trait_list(data, last_trait_offset, known)

        return cls(
            version=version,
            last_trait_offset=last_trait_offset,
            traits=traits,
            raw=data,
        )

    @property
    def trait_ids(self) -> list[int]:
        return list(self.traits)

    def describe(self) -> str:
        return (
            f"SimInfo(version={self.version}, last_trait_offset={self.last_trait_offset}, "
            f"traits={len(self.traits)})"
        )


def _find_trait_list(
    data: bytes,
    last_trait_offset: int,
    known: Optional[set[int]],
) -> list[int]:
    """Recover the ``count + uint64[]`` trait list ending at ``last_trait_offset``."""
    end = last_trait_offset + 8
    best: list[int] = []
    best_score = -1

    for count in range(1, 256):
        start = end - count * 8
        if start < 1:
            break
        if data[start - 1] != count:
            continue

        ids = [struct.unpack_from("<Q", data, start + index * 8)[0] for index in range(count)]
        if any(value == 0 for value in ids):
            continue

        if known is not None:
            recognised = sum(1 for value in ids if value in known)
            # Every value must be a known trait.  Unknown traits are possible
            # with incomplete mods, but a fully unknown list is a false positive.
            if recognised != count:
                continue
            score = count
        else:
            # Without a catalog, prefer lists of small-ish IDs; all real trait
            # IDs in this section are below 2^32.
            if any(value >= 1 << 32 for value in ids):
                continue
            score = count

        if score > best_score:
            best = ids
            best_score = score

    return best
