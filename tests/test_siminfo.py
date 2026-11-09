import struct

import pytest

from sims4_sdk.siminfo import SimInfo, SimInfoError


def build_siminfo(traits, *, version=38, padding=16):
    data = bytearray(8)
    data.extend(b"\x00" * padding)
    count_offset = len(data)
    data.append(len(traits))
    first_id_offset = len(data)
    for trait_id in traits:
        data.extend(struct.pack("<Q", trait_id))
    last_trait_offset = first_id_offset + max(0, len(traits) - 1) * 8
    struct.pack_into("<II", data, 0, version, last_trait_offset)
    return bytes(data)


def test_reads_trait_list() -> None:
    traits = [16838, 27454, 27915]
    info = SimInfo.parse(build_siminfo(traits), known_trait_ids=set(traits))
    assert info.version == 38
    assert info.traits == traits


def test_single_trait() -> None:
    info = SimInfo.parse(build_siminfo([27916]), known_trait_ids={27916})
    assert info.traits == [27916]


def test_unknown_ids_are_rejected() -> None:
    info = SimInfo.parse(build_siminfo([111, 222]), known_trait_ids={16838})
    assert info.traits == []


def test_without_catalog_uses_list_shape() -> None:
    info = SimInfo.parse(build_siminfo([16838, 27454]))
    assert info.traits == [16838, 27454]


def test_empty_list() -> None:
    info = SimInfo.parse(build_siminfo([]))
    assert info.traits == []


def test_too_small_raises() -> None:
    with pytest.raises(SimInfoError):
        SimInfo.parse(b"abc")


def test_describe() -> None:
    info = SimInfo.parse(build_siminfo([1]), known_trait_ids={1})
    assert "traits=1" in info.describe()
