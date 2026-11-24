"""Index JPEG artwork resources by instance ID across the installation."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .catalog.diagnostics import ExtractionIssue
from .core import DBPF, ResourceEntry, ResourceKey
from .export import Serializable
from .installation import Installation, PackageInfo
from .save.artwork import Artwork, decode_artwork

__all__ = [
    "IndexedArtwork",
    "ArtworkIndexResult",
    "ArtworkIndex",
    "LOT_THUMBNAIL_TYPES",
    "LotThumbnailIndex",
]

#: Static lot thumbnails keyed by house description ID: 256 and 400 pixels.
LOT_THUMBNAIL_TYPES = (0x0D338A3A, 0xA1FF2FC4)


@dataclass(frozen=True)
class IndexedArtwork(Serializable):
    """One decoded image; ``shared`` marks bytes reused by other instances."""

    key: ResourceKey
    package: PackageInfo
    artwork: Artwork
    shared: bool = False

    def to_dict(self, **options) -> dict:
        return {"key": str(self.key), "package_path": str(self.package.path),
                "pack": self.package.pack, "is_mod": self.package.is_mod,
                "shared": self.shared, "artwork": self.artwork.to_dict(**options)}


@dataclass
class ArtworkIndexResult(Serializable):
    images: list[IndexedArtwork] = field(default_factory=list)
    diagnostics: list[ExtractionIssue] = field(default_factory=list)

    def to_dict(self, **options) -> dict:
        return {"images": [image.to_dict(**options) for image in self.images],
                "diagnostics": [issue.to_dict(**options) for issue in self.diagnostics]}

    def largest(self, instance: int, *, unique: bool = False) -> Optional[IndexedArtwork]:
        """Return the largest image for an instance; ties go to the higher key.

        With ``unique``, images whose bytes other instances share (such as a
        placeholder) are skipped.
        """
        matches = (item for item in self.images
                   if item.key.instance == instance and not (unique and item.shared))
        return max(matches, key=lambda item: ((item.artwork.width or 0) *
                   (item.artwork.height or 0), item.key), default=None)


class ArtworkIndex:
    """Reusable package index; later packages win for the same full key.

    Create a fresh index after the package list or its contents change. Failed
    packages and resources are reported without dropping successfully read data.
    """

    def __init__(self, installation: Installation, type_ids: Iterable[int], *,
                 stage: str = "artwork"):
        self.stage = stage
        self._entries: dict[ResourceKey, tuple[PackageInfo, ResourceEntry]] = {}
        self.diagnostics: list[ExtractionIssue] = []
        wanted = frozenset(type_ids)
        for info in installation.packages:
            try:
                package = DBPF(info.path)
                for entry in package.iter_entries_for_types(wanted):
                    if not entry.is_null:
                        self._entries[entry.key] = (info, entry)
            except Exception as exc:
                self.diagnostics.append(ExtractionIssue.from_exception(
                    f"{stage}_index", exc, package_path=str(info.path), recoverable=True))

    @property
    def instances(self) -> set[int]:
        """Instance IDs with at least one indexed image."""
        return {key.instance for key in self._entries}

    def _shared_keys(self) -> set[ResourceKey]:
        return set()

    def read(self, instances: Iterable[int]) -> ArtworkIndexResult:
        """Decode variants for the given instance IDs, retaining failures."""
        wanted = set(instances)
        shared = self._shared_keys()
        result = ArtworkIndexResult(diagnostics=list(self.diagnostics))
        for key, (info, entry) in sorted(self._entries.items()):
            if key.instance not in wanted:
                continue
            try:
                artwork = decode_artwork(DBPF.read_entry(info.path, entry))
            except Exception as exc:
                result.diagnostics.append(ExtractionIssue.from_exception(
                    f"{self.stage}_read", exc, package_path=str(info.path),
                    resource_key=key, recoverable=True))
                continue
            result.images.append(IndexedArtwork(key, info, artwork, key in shared))
        return result


class LotThumbnailIndex(ArtworkIndex):
    """Static lot thumbnails shipped with the game, by house description ID.

    Look lots up with ``WorldLot.house_description_id``. Only some worlds ship
    them. Several lots share one placeholder at the larger size, which
    ``largest(..., unique=True)`` skips.
    """

    def __init__(self, installation: Installation):
        super().__init__(installation, LOT_THUMBNAIL_TYPES, stage="lot_thumbnail")
        self._shared: Optional[set[ResourceKey]] = None

    def _shared_keys(self) -> set[ResourceKey]:
        if self._shared is None:
            digests: dict[ResourceKey, bytes] = {}
            for key, (info, entry) in self._entries.items():
                try:
                    digests[key] = hashlib.blake2b(DBPF.read_entry(info.path, entry),
                                                   digest_size=16).digest()
                except Exception:
                    continue  # Reported when the image itself is read.
            counts = Counter((key.type_id, digest) for key, digest in digests.items())
            self._shared = {key for key, digest in digests.items()
                            if counts[key.type_id, digest] > 1}
        return self._shared
