from sims4_sdk.catalog import (
    Catalog,
    Preference,
    Trait,
    TuningSource,
)


def test_catalog_lookups_and_finalize() -> None:
    source = TuningSource(package="Test.package", pack="BASE")
    trait = Trait(
        id=1,
        name="trait_Test",
        display_name="Test",
        description=None,
        trait_type="PERSONALITY",
        source=source,
    )
    preference = Preference(
        id=2,
        name="trait_Test_Likes_Things",
        display_name="Likes Things",
        description=None,
        preference_type="LIKE",
        source=source,
    )
    catalog = Catalog(
        traits={trait.id: trait},
        preferences={preference.id: preference},
        strings={0x1234: "Hello"},
    ).finalize()

    assert catalog.trait(1) is trait
    assert catalog.trait("trait_Test") is trait
    assert catalog.preference(2) is preference
    assert catalog.preference("trait_Test_Likes_Things") is preference
    assert catalog.resolve_string("0x1234") == "Hello"
    assert catalog.resolve_string("plain") == "plain"
    assert catalog.resolve_string(None) is None
    assert "traits=1" in catalog.summary()


def test_preference_kind_helpers() -> None:
    like = Preference(
        id=1, name="a", display_name="A", description=None, preference_type="LIKE"
    )
    dislike = Preference(
        id=2, name="b", display_name="B", description=None, preference_type="DISLIKE"
    )
    assert like.is_like and not like.is_dislike
    assert dislike.is_dislike and not dislike.is_like


def test_tuning_source_label() -> None:
    assert TuningSource("a.package", "EP01").label == "EP01"
    assert TuningSource("a.package", "MOD", is_mod=True).label == "MOD:a.package"


def test_visible_traits_exclude_known_internal_and_preference_definitions() -> None:
    def make(id, name, kind="PERSONALITY", hidden=False):
        return Trait(id=id, name=name, display_name=name, description=None,
                     trait_type=kind, is_hidden=hidden)

    traits = [
        make(1, "trait_Good"),
        make(2, "trait_Walk", "walkstyle"),
        make(3, "trait_CustomHidden", hidden=True),
        make(4, "trait_GenderOptions_Frame_Feminine"),
        make(5, "trait_Species_Dog"),
        make(6, "trait_SimPreference_Likes_Music"),
        make(7, "trait_SeparatePreference"),
        make(8, "trait_Unclassified"),
    ]
    catalog = Catalog(
        traits={item.id: item for item in traits},
        preferences={7: Preference(id=7, name="preference", display_name="Preference", description=None, preference_type="LIKE")},
    )
    assert [item.id for item in catalog.visible_traits] == [1, 8]
    assert all(item.is_internal for item in traits[1:6])
    assert not traits[6].is_internal  # catalog-level overlap supplies this information
    assert traits[3].to_dict()["is_internal"] is True
    # Existing visible_only means is_hidden only; the new view is stricter.
    assert traits[1] in catalog.find_traits(visible_only=True)
