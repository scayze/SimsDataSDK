"""Source-backed extraction of save data without catalog resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..core import DBPF, ResourceKey
from ..exceptions import Sims4SDKError
from ..export import Serializable
from .artwork import ArtworkError, decode_artwork
from .protobuf import ProtobufError, decode
from .schema import SCHEMAS

SAVE_RESOURCE_TYPE = 0x0000000D
SAVE_ARTWORK_TYPES = frozenset({0x0F, 0x10, 0x12, 0x13, 0x14})
PERSISTENCE_RESOURCE_TYPE = 0x00000006


class SaveError(Sims4SDKError, ValueError):
    """Raised when a save file cannot be parsed."""


@dataclass
class SaveSource(Serializable):
    """Schema-selected save fields and their source, before interpretation.

    Unknown protobuf fields are not included; the resource can be retrieved
    from ``path`` and ``resource_key`` when the original bytes are needed.
    """

    path: Path
    decoded: dict[str, Any]
    resource_key: Optional[ResourceKey] = None
    artwork: dict = field(default_factory=dict)
    artwork_errors: list[dict[str, str]] = field(default_factory=list)
    relationship_coverage: str = "unknown"
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    @property
    def sims(self) -> list[dict[str, Any]]:
        return self.decoded.get("sims", [])


def extract_save(path: str | Path) -> SaveSource:
    """Decode source fields from a save without linking or deriving values."""
    path = Path(path)
    package = DBPF(path)
    entry = next(
        (entry for entry in package.entries if entry.key.type_id == SAVE_RESOURCE_TYPE),
        None,
    )
    if entry is None:
        raise SaveError(f"{path.name}: no SaveGameData resource (0x0000000D)")
    try:
        data = package.read_resource(entry)
        root = decode(data, "SaveGameData", SCHEMAS)
    except ProtobufError as exc:
        raise SaveError(f"{path.name}: {exc}") from exc
    source = SaveSource(path, root, entry.key)
    for persistence_entry in package.iter_entries(type_id=PERSISTENCE_RESOURCE_TYPE):
        if persistence_entry.is_null:
            continue
        source.relationship_coverage = "potentially_incomplete"
        source.diagnostics.append({
            "stage": "save_persistence",
            "code": "unsupported_persistence_resource",
            "message": ("Persistence resource is not decoded and may contain "
                        "relationship data; relationship results may be incomplete."),
            "path": str(path),
            "resource_key": str(persistence_entry.key),
            "recoverable": True,
            "unsupported_format": "type-0x00000006 persistence resource",
        })
    for image_entry in package.iter_entries_for_types(SAVE_ARTWORK_TYPES):
        if image_entry.is_null:
            continue
        try:
            source.artwork[image_entry.key] = decode_artwork(package.read_resource(image_entry))
        except (ArtworkError, OSError, Sims4SDKError) as exc:
            source.artwork_errors.append({"key": str(image_entry.key), "error": f"{type(exc).__name__}: {exc}"})
    return source


def extract_save_resource(data: bytes, name: str = "<memory>") -> SaveSource:
    """Decode a standalone SaveGameData payload, without package metadata."""
    return SaveSource(Path(name), decode(data, "SaveGameData", SCHEMAS))



