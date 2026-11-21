import pytest

from sims4_sdk.catalog import Catalog, LootBitOperation, PremadeBundle, PremadeRelationship, PremadeSim
from sims4_sdk.save import read_save_resource
from sims4_sdk.save.reader import sim_from_dict
from test_worlds import _bytes_field, _float_field, _varint, _varint_field


def _sim(sim_id, name, species):
    return (_varint_field(1, sim_id) + _bytes_field(5, name.encode())
            + _varint_field(60, species))


def _service_relationship(a, b, shared=(), a_bits=(), b_bits=(), object_id=None, track=None):
    def block(bits):
        return _bytes_field(1, b"".join(_varint(value) for value in bits)) if bits else b""
    shared_block = block(shared)
    if track is not None:
        shared_block += _bytes_field(3, _varint_field(1, track[0]) + _float_field(2, track[1]))
    record = (_varint_field(1, a) + _varint_field(2, b)
              + _bytes_field(3, shared_block) + _bytes_field(4, block(a_bits))
              + _bytes_field(5, block(b_bits)))
    if object_id is not None:
        record += _varint_field(7, object_id)
    return _bytes_field(1, record)


@pytest.mark.parametrize("species,owner_bit,pet_bit", [
    (2, 148060, 148061), (3, 148062, 148063),
    (4, 148060, 148061), (6, 321335, 321334),
])
def test_service_ownership_direction_and_packed_bits(species, owner_bit, pet_bit):
    relationships = (
        _service_relationship(1, 2, shared=[15803], a_bits=[pet_bit], b_bits=[owner_bit], track=(159228, 33.0))
        + _service_relationship(1, 3, shared=[pet_bit])
        + _service_relationship(2, 999, a_bits=[owner_bit])
        + _service_relationship(1, 4, a_bits=[pet_bit], object_id=20)
    )
    payload = (_bytes_field(2, _bytes_field(8, _bytes_field(13, relationships)))
               + _bytes_field(6, _sim(1, "Owner", 1))
               + _bytes_field(6, _sim(2, "Pet", species))
               + _bytes_field(6, _sim(3, "Other", 1))
               + _bytes_field(6, _sim(4, "Unrelated", 1)))
    save = read_save_resource(payload)
    owner, pet = save.sims[1], save.sims[2]
    assert owner.pet_ids == [2]
    assert pet.owner_ids == [1, 999]
    assert pet.is_animal is True and pet.is_pet is True
    assert owner.is_animal is False and owner.is_pet is False
    assert owner.relationships[0].shared_bits == [15803]
    assert owner.relationships[0].directional_bits == [pet_bit]
    assert [(x.track_id, x.value) for x in owner.relationships[0].track_values] == [(159228, 33.0)]
    assert pet.relationships[0].directional_bits == [owner_bit]
    assert 4 not in [relation.target_id for relation in owner.relationships]
    assert save.to_dict()["sims"]["2"]["owner_ids"] == [1, 999]
    assert '"is_pet": true' in pet.to_json()
    assert save.find_sims(is_pet=True) == [pet]
    assert save.find_sims(is_pet=False) == [owner, save.sims[3], save.sims[4]]


def test_species_classification_and_breed_values():
    assert (sim_from_dict({"sim_id": 1, "extended_species": 5}).is_animal,
            sim_from_dict({"sim_id": 1, "extended_species": 5}).is_pet) == (True, False)
    unknown = sim_from_dict({"sim_id": 2, "extended_species": 999})
    assert unknown.is_animal is None and unknown.is_pet is None
    sim = sim_from_dict({"sim_id": 3, "breed_name_key": 42}, Catalog(strings={42: "Arabian"}))
    assert (sim.breed_name, sim.breed_name_key) == ("Arabian", 42)
    sim = sim_from_dict({"sim_id": 3, "breed_name": "Custom", "breed_name_key": 42})
    assert sim.breed_name == "Custom"
    premade = PremadeSim(id=4, name="unknown", first_name="", last_name="")
    assert premade.is_pet is None and premade.to_dict()["is_animal"] is None
    horse = PremadeSim(id=5, name="horse", first_name="", last_name="", species_raw=6)
    bundle = PremadeBundle(sims=[premade, horse])
    assert bundle.find_sims(species="HORSE") == [horse]
    assert bundle.find_sims(is_pet=True) == [horse]
    assert bundle.find_sims(is_pet=False) == []


def test_static_directional_ownership_bits():
    from sims4_sdk.catalog.premades import _link_cross_household_and_ancestors

    owner = PremadeSim(id=1, name="Owner", first_name="", last_name="")
    pet = PremadeSim(id=2, name="Horse", first_name="", last_name="")
    catalog = Catalog(premade_relationships=[PremadeRelationship(
        sim_a=1, sim_b=2, bit_operations=[LootBitOperation(bit_id=321334)])])
    _link_cross_household_and_ancestors({1: owner, 2: pet}, {}, catalog)
    assert owner.pet_ids == [2] and pet.owner_ids == [1]
    assert pet.to_dict()["owner_ids"] == [1]


def test_legacy_tracker_pet_owner_without_catalog():
    sim = sim_from_dict({"sim_id": 2, "extended_species": 6, "attributes": {
        "relationship_tracker": {"relationships": [{"target_id": 1, "bits": [321335]}]}}})
    assert sim.owner_ids == [1]
    assert sim.relationships[0].directional_bits is None


def test_old_relationship_snapshots_gain_new_fields():
    from sims4_sdk.save.models import SavedRelationship

    relationship = SavedRelationship.__new__(SavedRelationship)
    relationship.__setstate__({"target_id": 1, "bits": [321335]})
    assert relationship.shared_bits == [] and relationship.directional_bits is None
