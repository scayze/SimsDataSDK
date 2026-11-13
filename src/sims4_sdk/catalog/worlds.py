"""World/lot manifests and pre-made household resources.

Two resources describe how a *new* save is populated.  Neither lives in the
``.world`` files (those only contain terrain, lot objects and art):

``0x729F6C4F`` — lot/household manifest
    One small record per lot.  It carries the lot name and description
    localization keys and, when a pre-made household lives on the lot, the
    household name/description keys plus a 64-bit reference to a
    ``0xB3C438F0`` resource.

``0xB3C438F0`` — pre-made household ("starter save")
    A protobuf document with the household funds and one message per member.
    Members carry their names, gender, age, traits, aspiration track, career and
    skill values.  This is where the older-pack pre-mades live (BFF, Pancakes,
    Caliente, Roomies, Spencer-Kim-Lewis, ...), which have no
    ``PremadeSimTemplate`` tuning at all.

Both resources appear in ``Data/Client/*.package`` and
``Delta/<PACK>/ClientDeltaBuild0.package``; the manifest is also duplicated in
the ``Simulation`` builds.  Scanning only ``Data/Simulation`` (as the SDK used
to) silently hides every household defined this way.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field, replace
from typing import Iterable, Mapping, Optional

from ..core import DBPF, LOT_MANIFEST_TYPE_ID, PREMADE_HOUSEHOLD_TYPE_ID, ResourceKey
from ..exceptions import Sims4SDKError
from ..installation import PackageInfo
from ..save.enums import FAMILY_RELATION_NAMES, OCCULT_FLAGS, names_for_flags
from ..save.models import SavedMilestone, SavedRelationship
from ..save.protobuf import ProtobufError, decode, iter_fields
from ..save.schema import SCHEMAS
from .diagnostics import ExtractionIssue
from .models import TuningSource

__all__ = [
    "WorldDataError",
    "LotRecord",
    "StarterCareer",
    "StarterMember",
    "StarterRelation",
    "StarterHouseholdRecord",
    "WorldData",
    "parse_lot_manifest",
    "parse_premade_household",
    "collect_world_data",
]

#: ``member.gender_flags`` bits observed in household resources.
_GENDER_FLAGS = {0x1000: "MALE", 0x2000: "FEMALE"}
#: ``member.age_flags`` bits.  The trait list also contains ``trait_<age>``,
#: which is preferred when present; this is only a fallback.
_AGE_FLAGS = {
    1: "BABY",
    2: "TODDLER",
    4: "CHILD",
    8: "TEEN",
    16: "YOUNGADULT",
    32: "ADULT",
    64: "ELDER",
}

_HOUSEHOLD_HEADER_SIZE = 8


class WorldDataError(Sims4SDKError, ValueError):
    """Raised when a lot manifest or household resource cannot be read."""


@dataclass
class LotRecord:
    """One record from a ``0x729F6C4F`` lot manifest."""

    instance: int
    lot_name_key: Optional[int] = None
    lot_description_key: Optional[int] = None
    household_name_key: Optional[int] = None
    household_description_key: Optional[int] = None
    household_id: Optional[int] = None
    record_size: int = 0
    source: Optional[TuningSource] = None
    raw: bytes = field(default=b"", repr=False)

    @property
    def has_household(self) -> bool:
        return self.household_id is not None

    def __repr__(self) -> str:
        name = f"0x{self.lot_name_key:08X}" if self.lot_name_key else None
        return f"LotRecord(instance=0x{self.instance:04X}, name={name}, household={self.household_id})"


@dataclass
class StarterCareer:
    """One career entry inside a ``0xB3C438F0`` household resource.

    ``track_level`` is the 0-based index into the career track's level list and
    matches ``SavedCareer.track_level``; ``display_level`` is the 1-based number
    shown in-game.
    """

    career_id: int
    track_id: int
    track_level: Optional[int] = None
    display_level: Optional[int] = None


@dataclass
class StarterRelation:
    """One genealogy entry (parent/grandparent) inside a household resource."""

    relation_type: int
    target_id: int

    @property
    def kind(self) -> str:
        return FAMILY_RELATION_NAMES.get(
            self.relation_type, f"UNKNOWN_{self.relation_type}"
        )

    def __repr__(self) -> str:
        return f"StarterRelation({self.kind}, target=0x{self.target_id:016X})"


@dataclass
class StarterMember:
    """One Sim inside a ``0xB3C438F0`` household resource."""

    first_name: str = ""
    last_name: str = ""
    sim_id: Optional[int] = None
    gender: Optional[str] = None
    age: Optional[str] = None
    body_blend: Optional[str] = None
    spouse_id: Optional[int] = None
    fiance_id: Optional[int] = None
    steady_ids: list[int] = field(default_factory=list)
    relationships: list[SavedRelationship] = field(default_factory=list)
    milestones: list[SavedMilestone] = field(default_factory=list)
    occult: list[str] = field(default_factory=list)
    degree: dict = field(default_factory=dict)
    trait_ids: list[int] = field(default_factory=list)
    aspiration_track_id: Optional[int] = None
    career_id: Optional[int] = None
    career_track_id: Optional[int] = None
    career_track_level: Optional[int] = None
    career_display_level: Optional[int] = None
    careers: list[StarterCareer] = field(default_factory=list)
    skills: list[tuple[int, float]] = field(default_factory=list)
    relations: list[StarterRelation] = field(default_factory=list)
    #: Localization keys in fields 55/56, even when resolution fails.
    first_name_key: Optional[int] = None
    last_name_key: Optional[int] = None
    _inline_first_name: str = field(default="", repr=False)
    _inline_last_name: str = field(default="", repr=False)

    def resolve_names(self, strings: Mapping[int, str]) -> None:
        """Resolve keyed names; inline names take precedence over STBL values.

        Missing keys remain available in ``first_name_key``/``last_name_key``.
        The method may be called again with a different locale's string table.
        """
        if self.first_name_key is not None:
            self.first_name = self._inline_first_name or strings.get(self.first_name_key, "")
        if self.last_name_key is not None:
            self.last_name = self._inline_last_name or strings.get(self.last_name_key, "")

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part)

    def __repr__(self) -> str:
        return f"StarterMember({self.full_name!r}, traits={len(self.trait_ids)})"


@dataclass
class StarterHouseholdRecord:
    """A parsed ``0xB3C438F0`` household resource."""

    instance: int
    name: str = ""
    funds: Optional[int] = None
    members: list[StarterMember] = field(default_factory=list)
    source: Optional[TuningSource] = None
    raw: bytes = field(default=b"", repr=False)

    def member(self, sim_id: int) -> Optional[StarterMember]:
        """Look up a member by the Sim ID stored in this resource."""
        return next((member for member in self.members if member.sim_id == sim_id), None)

    def __repr__(self) -> str:
        return f"StarterHouseholdRecord({self.name!r}, members={len(self.members)})"


@dataclass
class WorldData:
    """Lot manifests and pre-made households collected from packages."""

    lots: dict[int, LotRecord] = field(default_factory=dict)
    households: dict[int, StarterHouseholdRecord] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list, repr=False)
    _pending_lots: dict[tuple[int, Optional[ResourceKey]], tuple[bytes, Optional[TuningSource]]] = field(
        default_factory=dict, repr=False
    )
    _household_errors: dict[tuple[int, Optional[ResourceKey]], str] = field(default_factory=dict, repr=False)
    diagnostics: list[ExtractionIssue] = field(default_factory=list)
    _household_issues: dict[tuple[int, Optional[ResourceKey]], ExtractionIssue] = field(default_factory=dict, repr=False)
    #: Winners by full resource key, preserving resources in different groups.
    household_resources: dict[ResourceKey, StarterHouseholdRecord] = field(default_factory=dict)
    lot_resources: dict[ResourceKey, LotRecord] = field(default_factory=dict)

    def resolve_names(self, strings: Mapping[int, str]) -> None:
        """Resolve starter-member names against a selected locale's STBL map."""
        records = list(self.household_resources.values()) + list(self.households.values())
        seen: set[int] = set()
        for record in records:
            if id(record) in seen:
                continue
            seen.add(id(record))
            for member in record.members:
                member.resolve_names(strings)

    def find_members(self, sim_id: int) -> list[tuple[StarterHouseholdRecord, StarterMember]]:
        """Return all matching source records; the same ID can occur more than once."""
        records = list(self.household_resources.values())
        known_records = {id(record) for record in records}
        records.extend(record for record in self.households.values() if id(record) not in known_records)
        return [(record, member) for record in records
                for member in record.members if member.sim_id == sim_id]

    def add_household(
        self,
        instance: int,
        data: bytes,
        source: Optional[TuningSource] = None,
    ) -> None:
        resource_key = source.resource_key if source else None
        identity = (instance, resource_key)
        try:
            record = parse_premade_household(data, instance=instance, source=source)
        except WorldDataError as exc:
            self._household_errors[identity] = (
                f"pre-made household 0x{instance:016X}: {exc}"
            )
            self._household_issues[identity] = ExtractionIssue.from_exception(
                "household", exc, package_path=source.path if source else None,
                resource_key=source.resource_key if source else None,
            )
            return
        # A newer build of the same resource may have succeeded already.
        self._household_errors.pop(identity, None)
        self._household_issues.pop(identity, None)
        if resource_key is not None:
            self.household_resources[resource_key] = record
        self.households[instance] = record

    def add_lot(
        self,
        instance: int,
        data: bytes,
        source: Optional[TuningSource] = None,
    ) -> None:
        # Parsing needs the complete set of household instance IDs, so the raw
        # record is kept until :meth:`finalize`.
        if not data:
            return
        key = (instance, source.resource_key if source else None)
        # Reinsert an overridden key so the instance view follows load order.
        self._pending_lots.pop(key, None)
        self._pending_lots[key] = (data, source)

    def finalize(self) -> "WorldData":
        self.errors.extend(self._household_errors.values())
        self._household_errors.clear()
        self.diagnostics.extend(self._household_issues.values())
        self._household_issues.clear()
        household_ids = set(self.households)
        for (instance, resource_key), (data, source) in self._pending_lots.items():
            try:
                record = parse_lot_manifest(
                    data,
                    instance=instance,
                    household_ids=household_ids,
                    source=source,
                )
                self.lots[instance] = record
                if resource_key is not None:
                    self.lot_resources[resource_key] = record
            except WorldDataError as exc:
                self.errors.append(f"lot manifest 0x{instance:04X}: {exc}")
                self.diagnostics.append(ExtractionIssue.from_exception(
                    "lot_manifest", exc, package_path=source.path if source else None,
                    resource_key=source.resource_key if source else None,
                ))
        self._pending_lots.clear()
        return self

    def merge(self, other: "WorldData") -> "WorldData":
        self.lots.update(other.lots)
        self.households.update(other.households)
        self.lot_resources.update(other.lot_resources)
        self.household_resources.update(other.household_resources)
        self.errors.extend(other.errors)
        self.diagnostics.extend(other.diagnostics)
        return self

    def __repr__(self) -> str:
        return (
            f"WorldData(lots={len(self.lots)}, "
            f"households={len(self.households)}, errors={len(self.errors)})"
        )


# ----------------------------------------------------------------------
# lot manifest
# ----------------------------------------------------------------------
def parse_lot_manifest(
    data: bytes,
    *,
    instance: int = 0,
    household_ids: Optional[Iterable[int]] = None,
    strings: Optional[Mapping[int, str]] = None,
    source: Optional[TuningSource] = None,
) -> LotRecord:
    """Parse one ``0x729F6C4F`` record.

    The lot name and description keys are at fixed offsets.  The optional
    household block is located by scanning for a ``(name_key, description_key,
    uint64 household_id)`` triple; passing ``household_ids`` (the instances that
    actually exist) makes that detection exact.
    """
    if len(data) < 0x10:
        raise WorldDataError(f"record is too small ({len(data)} bytes)")

    lot_name_key = _u32(data, 0x04)
    lot_description_key = _u32(data, 0x08)

    record = LotRecord(
        instance=instance,
        lot_name_key=lot_name_key or None,
        lot_description_key=lot_description_key or None,
        record_size=len(data),
        source=source,
        raw=data,
    )

    block = _find_household_block(data, household_ids, strings)
    if block is None:
        return record

    record.household_name_key = _u32(data, block) or None
    record.household_description_key = _u32(data, block + 4) or None
    record.household_id = _u64(data, block + 8) or None
    return record


def _find_household_block(
    data: bytes,
    household_ids: Optional[Iterable[int]],
    strings: Optional[Mapping[int, str]],
) -> Optional[int]:
    ids = set(household_ids) if household_ids is not None else None
    for offset in range(0x0C, len(data) - 15):
        name_key = _u32(data, offset)
        description_key = _u32(data, offset + 4)
        household_id = _u64(data, offset + 8)
        if not household_id or not name_key or not description_key:
            continue
        if ids is not None:
            if household_id not in ids:
                continue
        elif strings is not None:
            if name_key not in strings or description_key not in strings:
                continue
        else:
            # Structural fallback for callers without a catalog: the block is
            # preceded by four zero bytes and a non-zero word.
            if _u32(data, offset - 4) != 0 or _u32(data, offset - 8) == 0:
                continue
        return offset
    return None


# ----------------------------------------------------------------------
# pre-made households
# ----------------------------------------------------------------------
def parse_premade_household(
    data: bytes,
    *,
    instance: int = 0,
    source: Optional[TuningSource] = None,
    strings: Optional[Mapping[int, str]] = None,
) -> StarterHouseholdRecord:
    """Parse one ``0xB3C438F0`` household resource.

    Two header layouts occur in the installed game (both little-endian):

    * version 0 — ``u32 version, u32 payload_length`` (8-byte header);
    * version 2 — three ``u32`` words then a length (16-byte header).

    Rather than trusting the length field, the payload offsets are tried in
    order and the first one that yields a household message wins.
    """
    if len(data) < _HOUSEHOLD_HEADER_SIZE:
        raise WorldDataError(f"resource is too small ({len(data)} bytes)")

    for payload in _candidate_payloads(data):
        record = _parse_household_payload(payload, instance, source)
        if record is not None:
            record.raw = data
            if strings is not None:
                for member in record.members:
                    member.resolve_names(strings)
            return record
    raise WorldDataError("household resource has no household message")


def _candidate_payloads(data: bytes) -> Iterable[bytes]:
    version = _u32(data, 0)
    preferred = {0: (8,), 2: (16,)}.get(version, (8, 16))
    seen: set[int] = set()
    for offset in preferred:
        if 0 <= offset < len(data):
            seen.add(offset)
            yield data[offset:]
    # Fallback: scan a short prefix for the protobuf start.
    for offset in range(4, min(len(data), 64)):
        if offset not in seen:
            seen.add(offset)
            yield data[offset:]


def _parse_household_payload(
    payload: bytes,
    instance: int,
    source: Optional[TuningSource],
) -> Optional[StarterHouseholdRecord]:
    try:
        fields = list(iter_fields(payload))
    except ProtobufError:
        return None

    household_blob = next(
        (value for number, wire, value in fields if number == 1 and wire == 2),
        None,
    )
    if household_blob is None:
        return None

    try:
        household = list(iter_fields(household_blob))
    except ProtobufError:
        return None

    name = _text(household, 3)
    if name is None and not any(number == 6 for number, _, _ in household):
        return None

    members = [
        _parse_member(value, index)
        for index, (number, wire, value) in enumerate(
            (item for item in household if item[0] == 6 and item[1] == 2), start=1
        )
    ]

    return StarterHouseholdRecord(
        instance=instance,
        name=name or "",
        funds=_varint(household, 4),
        members=members,
        source=source,
    )


def _parse_member(data: bytes, index: int) -> StarterMember:
    fields = _fields(data, f"household member {index}")

    member = StarterMember(
        first_name=_text(fields, 5) or "",
        last_name=_text(fields, 6) or "",
        sim_id=_fixed64(fields, 1),
        gender=_GENDER_FLAGS.get(_varint(fields, 7) or 0),
        age=_AGE_FLAGS.get(_varint(fields, 8) or 0),
        body_blend=_text(fields, 12),
        spouse_id=_integer(fields, 15) or None,
        fiance_id=_integer(fields, 68) or None,
        aspiration_track_id=_varint(fields, 34),
        first_name_key=_integer(fields, 55),
        last_name_key=_integer(fields, 56),
        _inline_first_name=_text(fields, 5) or "",
        _inline_last_name=_text(fields, 6) or "",
    )

    for number, wire, value in fields:
        if number == 30 and wire == 2:
            _parse_gameplay(value, member)
        elif number == 47 and wire == 2:
            from ..save.reader import _milestones

            gameplay = _decode_tracker(value, "GameplaySimData")
            member.milestones = _milestones(
                gameplay.get("developmental_milestone_tracker", {}), None
            )
        elif number == 72:
            if wire == 2:
                member.steady_ids.extend(_read_packed_varints(value))
            elif wire in (0, 1, 5):
                target = _integer([(number, wire, value)], number)
                if target is not None:
                    member.steady_ids.append(target)
    member.steady_ids = _dedupe(member.steady_ids)
    return member


def _parse_gameplay(data: bytes, member: StarterMember) -> None:
    try:
        fields = list(iter_fields(data))
    except ProtobufError as exc:
        raise WorldDataError(f"gameplay tracker: {exc}") from exc

    for number, wire, value in fields:
        if number == 1 and wire == 2:
            from ..save.reader import _relationships

            member.relationships.extend(
                _relationships(_decode_tracker(value, "PersistableRelationshipTracker"), None, {})
            )
        elif number == 17 and wire == 2:
            tracker = _decode_tracker(value, "PersistableOccultTracker")
            member.occult = names_for_flags(tracker.get("occult_types", 0), OCCULT_FLAGS)
        elif number == 30 and wire == 2:
            member.degree = _decode_tracker(value, "PersistableDegreeTracker")
        elif number == 10 and wire == 2:
            member.trait_ids.extend(_packed_traits(value))
        elif number == 12 and wire == 2:
            for entry in _submessages(value):
                career = _parse_career(entry)
                if career is not None:
                    member.careers.append(career)
        elif number == 13 and wire == 2:
            for entry in _submessages(value):
                skill = _parse_skill(entry)
                if skill is not None:
                    member.skills.append(skill)
        elif number == 14 and wire == 2:
            for entry in _submessages(value):
                relation = _parse_relation(entry)
                if relation is not None:
                    member.relations.append(relation)

    member.trait_ids = _dedupe(member.trait_ids)
    if member.careers:
        first = member.careers[0]
        member.career_id = first.career_id
        member.career_track_id = first.track_id
        member.career_track_level = first.track_level
        member.career_display_level = first.display_level


def _decode_tracker(data: bytes, schema: str) -> dict:
    try:
        return decode(data, schema, SCHEMAS)
    except ProtobufError as exc:
        raise WorldDataError(f"{schema}: {exc}") from exc


def _packed_traits(data: bytes) -> list[int]:
    """``gameplay.10`` is a message whose field 1 is packed trait IDs."""
    traits: list[int] = []
    for number, wire, value in _fields(data, "trait list"):
        if number == 1 and wire == 2:
            traits.extend(_read_packed_varints(value))
    return traits


def _submessages(data: bytes) -> list[bytes]:
    """Return the repeated ``field 1`` messages of a container message.

    ``gameplay.12``/``gameplay.13`` wrap their repeated career/skill entries in
    an extra message level, so the container holds ``field 1`` per entry.
    """
    try:
        fields = list(iter_fields(data))
    except ProtobufError:
        return []
    children = [value for number, wire, value in fields if number == 1 and wire == 2]
    if children:
        return children
    return [data]


def _parse_career(data: bytes) -> Optional[StarterCareer]:
    fields = _fields(data, "career")
    career_id = _varint(fields, 1)
    track_id = _varint(fields, 2)
    if career_id is None or track_id is None:
        return None
    return StarterCareer(
        career_id=career_id,
        track_id=track_id,
        track_level=_varint(fields, 3),
        display_level=_varint(fields, 4),
    )


def _parse_relation(data: bytes) -> Optional[StarterRelation]:
    fields = _fields(data, "family relation")
    relation_type = _integer(fields, 1)
    target_id = _integer(fields, 2)
    if relation_type is None or target_id is None:
        return None
    return StarterRelation(relation_type=relation_type, target_id=target_id)


def _parse_skill(data: bytes) -> Optional[tuple[int, float]]:
    fields = _fields(data, "skill")
    skill_id = _varint(fields, 1)
    value: Optional[float] = None
    for number, wire, raw in fields:
        if number != 2:
            continue
        if wire == 5 and len(raw) == 4:
            value = struct.unpack("<f", raw)[0]
        elif wire == 1 and len(raw) == 8:
            value = struct.unpack("<d", raw)[0]
        elif wire == 0:
            value = float(raw)
    if skill_id is None or value is None:
        return None
    return skill_id, value


# ----------------------------------------------------------------------
# package scanning
# ----------------------------------------------------------------------
def collect_world_data(
    packages: Iterable[PackageInfo],
    *,
    progress=None,
) -> WorldData:
    """Read both resource types from ``packages`` without touching tuning.

    Kept as a standalone helper; :func:`sims4_sdk.catalog.builder.collect_package_data`
    fuses this with the tuning scan so packages are only opened once.
    """
    world = WorldData()
    for info in packages:
        if progress:
            progress(f"  world: {info.label}: {info.path.name}")
        try:
            package = DBPF(info.path)
        except Exception as exc:
            world.diagnostics.append(ExtractionIssue.from_exception(
                "package_open", exc, package_path=str(info.path)
            ))
            continue
        source = TuningSource(
            package=str(info.path.name),
            pack=info.pack,
            is_mod=info.is_mod,
            path=str(info.path),
        )
        add_package_world_resources(world, package, source)
    return world.finalize()


def add_package_world_resources(
    world: WorldData,
    package: DBPF,
    source: TuningSource,
) -> None:
    """Add one already-open package's world resources to ``world``.

    Used by :func:`sims4_sdk.catalog.builder.collect_package_data` so the DBPF
    index is parsed once per package.
    """
    for entry in package.iter_entries_for_types({PREMADE_HOUSEHOLD_TYPE_ID, LOT_MANIFEST_TYPE_ID}):
        entry_source = replace(source, resource_key=entry.key)
        try:
            raw = package.read_resource(entry)
        except Exception as exc:
            world.diagnostics.append(ExtractionIssue.from_exception(
                "resource_read", exc, package_path=source.path, resource_key=entry.key
            ))
            continue
        if entry.key.type_id == PREMADE_HOUSEHOLD_TYPE_ID:
            world.add_household(entry.key.instance, raw, entry_source)
        else:
            world.add_lot(entry.key.instance, raw, entry_source)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _fields(data: bytes, context: str) -> list[tuple[int, int, object]]:
    try:
        return list(iter_fields(data))
    except ProtobufError as exc:
        raise WorldDataError(f"{context}: {exc}") from exc


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def _text(fields, number: int) -> Optional[str]:
    for field_number, wire, value in fields:
        if field_number == number and wire == 2:
            return value.decode("utf-8", errors="replace")
    return None


def _varint(fields, number: int) -> Optional[int]:
    for field_number, wire, value in fields:
        if field_number == number and wire == 0:
            return int(value)
    return None


def _integer(fields, number: int) -> Optional[int]:
    """Read a field encoded as varint, fixed64 or fixed32."""
    for field_number, wire, value in fields:
        if field_number != number:
            continue
        if wire == 0:
            return int(value)
        if wire == 1 and len(value) == 8:
            return int.from_bytes(value, "little")
        if wire == 5 and len(value) == 4:
            return int.from_bytes(value, "little")
    return None


def _fixed64(fields, number: int) -> Optional[int]:
    for field_number, wire, value in fields:
        if field_number == number and wire == 1 and len(value) == 8:
            return int.from_bytes(value, "little")
    return None


def _read_packed_varints(data: bytes) -> list[int]:
    values: list[int] = []
    position = 0
    total = len(data)
    while position < total:
        result = 0
        shift = 0
        while position < total and shift < 70:
            byte = data[position]
            position += 1
            result |= (byte & 0x7F) << shift
            if not byte & 0x80:
                values.append(result)
                break
            shift += 7
        else:
            break
    return values


def _dedupe(values: list[int]) -> list[int]:
    return list(dict.fromkeys(values))
