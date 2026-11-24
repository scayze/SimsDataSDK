"""Read premade household composites using the installation package order."""

from __future__ import annotations

from .artwork_index import ArtworkIndex, ArtworkIndexResult, IndexedArtwork
from .installation import Installation

__all__ = ["PREMADE_COMPOSITE_TYPE", "PremadeCompositeIndex", "IndexedArtwork",
           "ArtworkIndexResult"]

PREMADE_COMPOSITE_TYPE = 0x3BD45407


class PremadeCompositeIndex(ArtworkIndex):
    """Household composites keyed by household resource (``0xB3C438F0``) instance.

    The instance may differ from the tuning ID exposed by ``PremadeHousehold.id``.
    """

    def __init__(self, installation: Installation):
        super().__init__(installation, (PREMADE_COMPOSITE_TYPE,), stage="composite")
