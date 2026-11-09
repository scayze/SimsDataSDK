import pytest

from sims4_sdk.core import (
    CombinedTuning,
    CombinedTuningError,
    TuningElement,
    is_binary_tuning,
)

XML = """<?xml version="1.0" encoding="utf-8"?>
<combined>
  <g>
    <T x="1">Hello</T>
    <L x="2"><T>One</T><T>Two</T></L>
  </g>
  <I c="Trait" i="trait" m="traits.traits" n="trait_Test" s="1234">
    <r n="display_name" x="1" />
    <r n="tags" x="2" />
    <T n="is_hidden">True</T>
    <T n="points">42</T>
    <T n="weight">1.5</T>
  </I>
  <I c="Aspiration" i="aspiration" m="aspirations.aspirations" n="asp_Test" s="0x10" />
  <NotTuning />
</combined>
"""


@pytest.fixture()
def tuning() -> CombinedTuning:
    return CombinedTuning.from_xml(XML)


def test_basic_queries(tuning: CombinedTuning) -> None:
    assert len(tuning) == 2
    assert tuning.by_class("Trait")[0].name == "trait_Test"
    assert tuning.by_module("aspirations.aspirations")[0].name == "asp_Test"
    assert tuning.by_tuning_type("trait")[0].name == "trait_Test"
    assert tuning.find_by_name("asp_Test").cls == "Aspiration"
    assert tuning.find_by_instance_id(1234).name == "trait_Test"
    assert tuning.find_by_instance_id(0x10).name == "asp_Test"
    assert tuning.find_by_name("nope") is None


def test_indexes(tuning: CombinedTuning) -> None:
    by_id = tuning.index_by_instance_id()
    by_name = tuning.index_by_name()
    assert by_id[1234].name == "trait_Test"
    assert by_name["asp_Test"].instance_id == 0x10
    assert len(tuning.references) == 2


def test_reference_resolution(tuning: CombinedTuning) -> None:
    trait: TuningElement = tuning.find_by_name("trait_Test")
    assert trait.get_value("display_name") == "Hello"
    assert trait.get_list("tags") == ["One", "Two"]
    assert trait.get_bool("is_hidden") is True
    assert trait.get_int("points") == 42
    assert trait.get_float("weight") == pytest.approx(1.5)
    assert trait.get_value("missing") is None
    assert trait.get_bool("missing", default=True) is True
    assert trait.get_list("missing") == []


def test_to_dict(tuning: CombinedTuning) -> None:
    trait = tuning.find_by_name("trait_Test")
    assert trait.to_dict() == {
        "class": "Trait",
        "tuning_type": "trait",
        "module": "traits.traits",
        "name": "trait_Test",
        "instance_id": 1234,
    }


def test_parse_bytes(tuning: CombinedTuning) -> None:
    parsed = CombinedTuning.parse(XML.encode("utf-8"))
    assert len(parsed) == 2


def test_invalid_xml_raises() -> None:
    with pytest.raises(CombinedTuningError):
        CombinedTuning.from_xml("<combined><I c='Trait'>")


def test_is_binary_tuning() -> None:
    assert is_binary_tuning(b"DATA\x00\x01\x00\x00")
    assert not is_binary_tuning(b"<?xml version='1.0'?>")
