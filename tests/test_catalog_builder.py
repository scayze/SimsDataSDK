"""Unit tests for catalog package collection."""

from __future__ import annotations

import pytest

from sims4_sdk.catalog import collect_package_data
from sims4_sdk.core import COMBINED_TUNING_TYPE_ID, CombinedTuning
from sims4_sdk.installation import PackageInfo

from conftest import build_package

XML = """<?xml version="1.0" encoding="utf-8"?>
<combined>
  <I c="Trait" i="trait" m="traits.traits" n="trait_Test" s="1234">
    <T n="display_name">Test</T>
  </I>
</combined>
"""

OTHER_XML = """<?xml version="1.0" encoding="utf-8"?>
<combined>
  <I c="Trait" i="trait" m="traits.traits" n="trait_Other" s="5678">
    <T n="display_name">Other</T>
  </I>
</combined>
"""


def _package(tmp_path, name: str, payload: bytes) -> PackageInfo:
    path = tmp_path / name
    path.write_bytes(
        build_package(
            [
                {
                    "type": COMBINED_TUNING_TYPE_ID,
                    "group": 0,
                    "instance": 1,
                    "data": payload,
                    "compression": "zlib",
                }
            ]
        )
    )
    return PackageInfo(path, "BASE")


def test_identical_combined_tuning_is_parsed_once(tmp_path, monkeypatch) -> None:
    packages = [
        _package(tmp_path, "SimulationPreload.package", XML.encode("utf-8")),
        _package(tmp_path, "SimulationDeltaBuild0.package", XML.encode("utf-8")),
    ]

    calls = []
    original = CombinedTuning.parse

    def counting_parse(data: bytes) -> CombinedTuning:
        calls.append(data)
        return original(data)

    monkeypatch.setattr(CombinedTuning, "parse", staticmethod(counting_parse))

    data = collect_package_data(packages, include_world=False)

    assert len(calls) == 1
    assert data.entries[1234].name == "trait_Test"


def test_different_combined_tuning_is_parsed_separately(tmp_path, monkeypatch) -> None:
    packages = [
        _package(tmp_path, "a.package", XML.encode("utf-8")),
        _package(tmp_path, "b.package", OTHER_XML.encode("utf-8")),
    ]

    calls = []
    original = CombinedTuning.parse

    def counting_parse(data: bytes) -> CombinedTuning:
        calls.append(data)
        return original(data)

    monkeypatch.setattr(CombinedTuning, "parse", staticmethod(counting_parse))

    data = collect_package_data(packages, include_world=False)

    assert len(calls) == 2
    assert set(data.entries) == {1234, 5678}
