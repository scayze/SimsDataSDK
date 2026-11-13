"""Read premade household composites using the installation package order."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from .catalog.diagnostics import ExtractionIssue
from .core import DBPF, ResourceEntry, ResourceKey
from .installation import Installation, PackageInfo
from .save.artwork import Artwork, decode_artwork
from .export import Serializable

PREMADE_COMPOSITE_TYPE = 0x3BD45407


@dataclass(frozen=True)
class PremadeComposite(Serializable):
    key: ResourceKey
    package: PackageInfo
    artwork: Artwork

    def to_dict(self, **options) -> dict:
        return {"key": str(self.key), "package_path": str(self.package.path),
                "pack": self.package.pack, "is_mod": self.package.is_mod,
                "artwork": self.artwork.to_dict(**options)}


@dataclass
class PremadeCompositeResult(Serializable):
    images: list[PremadeComposite] = field(default_factory=list)
    diagnostics: list[ExtractionIssue] = field(default_factory=list)

    def to_dict(self, **options) -> dict:
        return {"images": [image.to_dict(**options) for image in self.images],
                "diagnostics": [issue.to_dict(**options) for issue in self.diagnostics]}

    def largest(self, template_id: int) -> Optional[PremadeComposite]:
        """Return the largest known dimensions, breaking ties by resource key."""
        matches = (item for item in self.images if item.key.instance == template_id)
        return max(matches, key=lambda item: ((item.artwork.width or 0) *
                   (item.artwork.height or 0), item.key), default=None)


class PremadeCompositeIndex:
    """Reusable package index; later packages win for the same full key.

    Create a fresh index after the package list or its contents change. Failed
    packages and resources are reported without dropping successfully read data.
    """

    def __init__(self, installation: Installation):
        self._entries: dict[ResourceKey, tuple[PackageInfo, ResourceEntry]] = {}
        self.diagnostics: list[ExtractionIssue] = []
        for info in installation.packages:
            try:
                package = DBPF(info.path)
                for entry in package.iter_entries(type_id=PREMADE_COMPOSITE_TYPE):
                    if not entry.is_null:
                        self._entries[entry.key] = (info, entry)
            except Exception as exc:
                self.diagnostics.append(ExtractionIssue.from_exception(
                    "composite_index", exc, package_path=str(info.path), recoverable=True))

    def read(self, template_ids: Iterable[int]) -> PremadeCompositeResult:
        """Decode all variants for requested template IDs, retaining failures."""
        wanted = set(template_ids)
        result = PremadeCompositeResult(diagnostics=list(self.diagnostics))
        for key, (info, entry) in sorted(self._entries.items()):
            if key.instance not in wanted:
                continue
            try:
                artwork = decode_artwork(DBPF.read_entry(info.path, entry))
            except Exception as exc:
                result.diagnostics.append(ExtractionIssue.from_exception(
                    "composite_read", exc, package_path=str(info.path),
                    resource_key=key, recoverable=True))
                continue
            result.images.append(PremadeComposite(key, info, artwork))
        return result
