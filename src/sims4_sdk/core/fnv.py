"""FNV hashing helpers used throughout The Sims 4.

The Sims 4 derives most identifiers from names:

* **FNV-1 64-bit** — tuning instance IDs (``s`` attribute of a tuning ``<I>``).
* **FNV-1 32-bit** — STBL string keys and many resource references.

The game uses classic FNV-1 (multiply, then XOR), *not* FNV-1a.  Both variants are
provided because third-party tools occasionally use FNV-1a.
"""

from __future__ import annotations

FNV_32_OFFSET_BASIS = 0x811C9DC5
FNV_32_PRIME = 0x01000193
FNV_64_OFFSET_BASIS = 0xCBF29CE484222325
FNV_64_PRIME = 0x00000100000001B3

_MASK_32 = 0xFFFFFFFF
_MASK_64 = 0xFFFFFFFFFFFFFFFF


def _to_bytes(value: str | bytes) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise TypeError(f"expected str or bytes, got {type(value).__name__}")


def fnv1_32(value: str | bytes, *, offset_basis: int = FNV_32_OFFSET_BASIS) -> int:
    """Return the 32-bit FNV-1 hash of ``value``."""
    data = _to_bytes(value)
    result = offset_basis & _MASK_32
    for byte in data:
        result = (result * FNV_32_PRIME) & _MASK_32
        result ^= byte
    return result


def fnv1a_32(value: str | bytes, *, offset_basis: int = FNV_32_OFFSET_BASIS) -> int:
    """Return the 32-bit FNV-1a hash of ``value``."""
    data = _to_bytes(value)
    result = offset_basis & _MASK_32
    for byte in data:
        result ^= byte
        result = (result * FNV_32_PRIME) & _MASK_32
    return result


def fnv1_64(value: str | bytes, *, offset_basis: int = FNV_64_OFFSET_BASIS) -> int:
    """Return the 64-bit FNV-1 hash of ``value``."""
    data = _to_bytes(value)
    result = offset_basis & _MASK_64
    for byte in data:
        result = (result * FNV_64_PRIME) & _MASK_64
        result ^= byte
    return result


def fnv1a_64(value: str | bytes, *, offset_basis: int = FNV_64_OFFSET_BASIS) -> int:
    """Return the 64-bit FNV-1a hash of ``value``."""
    data = _to_bytes(value)
    result = offset_basis & _MASK_64
    for byte in data:
        result ^= byte
        result = (result * FNV_64_PRIME) & _MASK_64
    return result


def hash32(value: str | bytes) -> int:
    """Alias for the variant used by The Sims 4 for 32-bit hashes."""
    return fnv1_32(value)


def hash64(value: str | bytes) -> int:
    """Alias for the variant used by The Sims 4 for tuning instance IDs."""
    return fnv1_64(value)
