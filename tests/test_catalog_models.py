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
