"""Decode Tray records before linking catalog definitions or other files."""

from dataclasses import dataclass
from pathlib import Path
import struct
from typing import Any

from ..exceptions import Sims4SDKError
from ..export import Serializable
from .protobuf import ProtobufError, decode
from .schema import SCHEMAS


class TrayError(Sims4SDKError, ValueError):
    """A Tray file could not be parsed."""


@dataclass
class TraySource(Serializable):
    path: Path
    kind: str
    decoded: dict[str, Any]
    payload_offset: int


def extract_tray_item(path: str | Path) -> TraySource:
    path = Path(path)
    data = path.read_bytes()
    if len(data) < 8:
        raise TrayError(f"{path.name}: file is too small")
    _, length = struct.unpack_from("<II", data, 0)
    payload = data[8:8 + length] if 0 < length <= len(data) - 8 else data[8:]
    try:
        decoded = decode(payload, "TrayItem", SCHEMAS)
    except ProtobufError as exc:
        raise TrayError(f"{path.name}: {exc}") from exc
    return TraySource(path, "item", decoded, 8)


def extract_household_binary(path: str | Path) -> TraySource:
    path = Path(path)
    data = path.read_bytes()
    last_error = None
    for offset in (16, 12, 8, 0):
        if offset >= len(data):
            continue
        try:
            decoded = decode(data[offset:], "FamilyData", SCHEMAS)
        except ProtobufError as exc:
            last_error = exc
            continue
        if decoded.get("family_account") is not None:
            return TraySource(path, "household", decoded, offset)
    raise TrayError(f"{path.name}: could not decode FamilyData ({last_error})")
