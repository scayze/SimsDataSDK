"""Unit tests for lot manifests (``0x729F6C4F``) and household resources."""

from __future__ import annotations

import struct

from sims4_sdk.catalog import (
    WorldData,
    WorldDataError,
    parse_lot_manifest,
    parse_premade_household,
)


# ----------------------------------------------------------------------
# tiny protobuf writer
# ----------------------------------------------------------------------
def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _field(number: int, wire: int, payload: bytes) -> bytes:
    return _varint((number << 3) | wire) + payload


def _bytes_field(number: int, payload: bytes) -> bytes:
    return _field(number, 2, _varint(len(payload)) + payload)


def _varint_field(number: int, value: int) -> bytes:
    return _field(number, 0, _varint(value))


def _fixed64_field(number: int, value: int) -> bytes:
    return _field(number, 1, struct.pack("<Q", value))


def _float_field(number: int, value: float) -> bytes:
    return _field(number, 5, struct.pack("<f", value))


def _member(
    first: str,
    last: str,
    *,
    sim_id: int,
    gender: int = 0x1000,
    age: int = 16,
    traits: tuple[int, ...] = (),
    skills: tuple[tuple[int, float], ...] = (),
    career: tuple[int, int] | None = None,
    aspiration: int | None = None,
    body_blend: str = "0.1,0.0,",
    spouse_id: int | None = None,
    relations: tuple[tuple[int, int], ...] = (),
) -> bytes:
    gameplay = b""
    if traits:
        packed = b"".join(_varint(value) for value in traits)
        gameplay += _bytes_field(10, _bytes_field(1, packed))
    if career is not None:
        entry = _varint_field(1, career[0]) + _varint_field(2, career[1])
        if len(career) > 2:
            entry += _varint_field(3, career[2])
        if len(career) > 3:
            entry += _varint_field(4, career[3])
        gameplay += _bytes_field(12, _bytes_field(1, entry))
    if skills:
        entries = b"".join(
            _bytes_field(1, _varint_field(1, skill_id) + _float_field(2, value))
            for skill_id, value in skills
        )
        gameplay += _bytes_field(13, entries)
    if relations:
        entries = b"".join(
            _bytes_field(
                1, _varint_field(1, relation_type) + _varint_field(2, target_id)
            )
            for relation_type, target_id in relations
        )
        gameplay += _bytes_field(14, entries)

    message = (
        _fixed64_field(1, sim_id)
        + _bytes_field(5, first.encode("utf-8"))
        + _bytes_field(6, last.encode("utf-8"))
        + _varint_field(7, gender)
        + _varint_field(8, age)
        + _bytes_field(12, body_blend.encode("utf-8"))
    )
    if spouse_id is not None:
        message += _fixed64_field(15, spouse_id)
    if gameplay:
        message += _bytes_field(30, gameplay)
    if aspiration is not None:
        message += _varint_field(34, aspiration)
    return message


def _household(members: list[bytes], *, name: str = "BFF", funds: int = 9000) -> bytes:
    household = (
        _varint_field(1, 1)
        + _varint_field(2, 0x01D9A0186BAD30CD)
        + _bytes_field(3, name.encode("utf-8"))
        + _varint_field(4, funds)
        + _varint_field(5, 0)
    )
    for member in members:
        household += _bytes_field(6, member)
    return household


def _v0resource(payload: bytes) -> bytes:
    return struct.pack("<II", 0, len(payload)) + payload


def _v2resource(payload: bytes) -> bytes:
    return struct.pack("<IIII", 2, 0, 0, len(payload) - 1) + payload


MEMBERS = [
    _member(
        "Travis",
        "Scott",
        sim_id=0x0173004006E01333,
        gender=0x1000,
        age=16,
        traits=(27086, 34318, 16841),
        skills=((16704, 100.0), (16703, 1540.0)),
        career=(27932, 32475, 1, 2),
        aspiration=25441,
    ),
    _member(
        "Liberty",
        "Lee",
        sim_id=0x0173004006E01334,
        gender=0x2000,
        age=16,
        traits=(27086, 27916, 16832),
        skills=((16706, 1540.0),),
        aspiration=25442,
    ),
]


def test_parse_premade_household_v0() -> None:
    payload = _bytes_field(1, _household(MEMBERS))
    record = parse_premade_household(_v0resource(payload), instance=0x01D9A0186BAD30CD)

    assert record.name == "BFF"
    assert record.raw == _v0resource(payload)
    assert record.funds == 9000
    assert [member.full_name for member in record.members] == [
        "Travis Scott",
        "Liberty Lee",
    ]

    travis = record.members[0]
    assert travis.sim_id == 0x0173004006E01333
    assert travis.gender == "MALE"
    assert travis.age == "YOUNGADULT"
    assert travis.trait_ids == [27086, 34318, 16841]
    assert travis.aspiration_track_id == 25441
    assert travis.career_id == 27932
    assert travis.career_track_id == 32475
    assert travis.career_track_level == 1
    assert travis.career_display_level == 2
    assert travis.skills == [(16704, 100.0), (16703, 1540.0)]
    assert travis.body_blend == "0.1,0.0,"

    liberty = record.members[1]
    assert liberty.gender == "FEMALE"
    assert liberty.career_id is None


def test_parse_premade_household_v2_header() -> None:
    payload = _bytes_field(1, _household(MEMBERS))
    record = parse_premade_household(_v2resource(payload), instance=1)
    assert record.name == "BFF"
    assert len(record.members) == 2


def test_starter_localized_name_keys_and_resolution() -> None:
    from sims4_sdk.catalog.models import Catalog
    from sims4_sdk.catalog.premades import build_premades
    from sims4_sdk.catalog.static import StaticData

    keyed = (_member("", "", sim_id=101) + _varint_field(55, 1001)
             + _field(56, 5, struct.pack("<I", 1002)))
    inline = (_member("Inline", "", sim_id=102) + _varint_field(55, 1003)
              + _varint_field(56, 1004))
    payload = _bytes_field(1, _household([keyed, inline], name="Family"))
    record = parse_premade_household(_v0resource(payload), instance=9,
                                     strings={1001: "First", 1002: "Last", 1003: "Ignored"})
    first, second = record.members
    assert first.full_name == "First Last"
    assert (first.first_name_key, first.last_name_key) == (1001, 1002)
    assert second.first_name == "Inline" and second.last_name == ""
    assert second.last_name_key == 1004  # unresolved, not an empty encoded name

    world = WorldData(households={9: record})
    catalog = Catalog(strings={1001: "Autre", 1002: "Nom", 1004: "Famille"})
    bundle = build_premades(None, catalog, {}, {}, world=world, siminfo_index={})
    assert {sim.full_name for sim in bundle.sims} == {"Autre Nom", "Inline Famille"}
    exported = StaticData(catalog=catalog, premades=bundle, world=world).to_dict()
    members = exported["world"]["households"]["9"]["members"]
    assert members[0]["first_name_key"] == 1001
    assert members[1]["last_name_key"] == 1004

    world.resolve_names({})
    assert first.full_name == "" and second.full_name == "Inline"
    assert first.first_name_key == 1001


def test_parse_premade_household_family() -> None:
    mother = _member("Bella", "Goth", sim_id=2, gender=0x2000, age=32)
    father = _member(
        "Mortimer", "Goth", sim_id=3, gender=0x1000, age=32, spouse_id=2
    )
    child = _member(
        "Cassandra",
        "Goth",
        sim_id=4,
        gender=0x2000,
        age=8,
        relations=((0, 2), (1, 3), (3, 5)),
    )
    payload = _bytes_field(1, _household([mother, father, child], name="Goth", funds=45500))
    record = parse_premade_household(_v0resource(payload), instance=2)

    mortimer = record.members[1]
    assert mortimer.spouse_id == 2

    cassandra = record.members[2]
    assert [(rel.kind, rel.target_id) for rel in cassandra.relations] == [
        ("MOTHER", 2),
        ("FATHER", 3),
        ("MOTHERS_FATHER", 5),
    ]


def test_starter_tracker_fields() -> None:
    track = _varint_field(1, 166) + _float_field(2, 42.5)
    relationship = _varint_field(1, 456) + _varint_field(3, 789) + _bytes_field(5, track)
    attributes = (
        _bytes_field(1, _bytes_field(1, relationship))
        + _bytes_field(17, _varint_field(1, 4))
        + _bytes_field(30, _varint_field(1, 1234))
    )
    milestone = _varint_field(1, 321) + _varint_field(2, 2)
    gameplay = _bytes_field(27, _bytes_field(1, milestone))
    member = (_member("A", "B", sim_id=1) + _bytes_field(30, attributes)
              + _bytes_field(47, gameplay) + _varint_field(68, 456)
              + _bytes_field(72, _varint(456) + _varint(789)))
    record = parse_premade_household(_v0resource(_bytes_field(1, _household([member]))))
    sim = record.members[0]
    assert sim.fiance_id == 456 and sim.steady_ids == [456, 789]
    assert sim.relationships[0].target_id == 456
    assert sim.relationships[0].bits == [789]
    assert sim.relationships[0].track_values[0].value == 42.5
    assert sim.milestones[0].milestone_id == 321 and sim.milestones[0].state == 2
    assert sim.occult == ["VAMPIRE"] and sim.degree["current_major"] == 1234


def test_parse_premade_household_rejects_garbage() -> None:
    try:
        parse_premade_household(b"\x00\x00\x00\x00\x01\x00\x00\x00\xff\xff")
    except WorldDataError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected WorldDataError")


def _manifest(
    *,
    lot_name_key: int = 0xDA1A6F1A,
    lot_description_key: int = 0xEE9B4780,
    household_name_key: int = 0x03E5EB05,
    household_description_key: int = 0x1658A3DA,
    household_id: int | None = 0x01D9A0186BAD30CD,
    size: int = 94,
) -> bytes:
    record = bytearray(size)
    struct.pack_into("<II", record, 0, 7, lot_name_key)
    struct.pack_into("<I", record, 8, lot_description_key)
    block = size - 16
    if household_id is not None:
        struct.pack_into("<I", record, block - 8, 0x50AB)
        struct.pack_into("<I", record, block, household_name_key)
        struct.pack_into("<I", record, block + 4, household_description_key)
        struct.pack_into("<Q", record, block + 8, household_id)
    return bytes(record)


def test_parse_lot_manifest_with_household() -> None:
    record = parse_lot_manifest(
        _manifest(),
        instance=0x7A4E,
        household_ids={0x01D9A0186BAD30CD},
    )
    assert record.lot_name_key == 0xDA1A6F1A
    assert record.lot_description_key == 0xEE9B4780
    assert record.household_name_key == 0x03E5EB05
    assert record.household_description_key == 0x1658A3DA
    assert record.household_id == 0x01D9A0186BAD30CD
    assert record.has_household


def test_parse_lot_manifest_without_household() -> None:
    record = parse_lot_manifest(_manifest(household_id=None), instance=0x7A4D)
    assert record.lot_name_key == 0xDA1A6F1A
    assert record.household_id is None
    assert not record.has_household


def test_parse_lot_manifest_ignores_unknown_household_reference() -> None:
    record = parse_lot_manifest(_manifest(), instance=1, household_ids=set())
    assert record.household_id is None


def test_parse_lot_manifest_uses_strings_without_household_ids() -> None:
    record = parse_lot_manifest(
        _manifest(),
        instance=1,
        strings={
            0xDA1A6F1A: "Garden Essence",
            0xEE9B4780: "A sprawling colonial.",
            0x03E5EB05: "BFF",
            0x1658A3DA: "Free spirit Liberty...",
        },
    )
    assert record.household_name_key == 0x03E5EB05


def test_world_data_ignores_empty_lot_records() -> None:
    world = WorldData()
    world.add_lot(1, b"")
    world.finalize()
    assert world.lots == {}
    assert world.errors == []


def test_world_lookup_preserves_multiple_records_with_same_sim_id() -> None:
    from sims4_sdk.catalog import StarterHouseholdRecord, StarterMember

    first = StarterHouseholdRecord(instance=1, members=[StarterMember(sim_id=10)])
    second = StarterHouseholdRecord(instance=2, members=[StarterMember(sim_id=10)])
    world = WorldData(households={1: first, 2: second})
    assert world.find_members(10) == [(first, first.members[0]), (second, second.members[0])]
    assert world.find_members(99) == []
