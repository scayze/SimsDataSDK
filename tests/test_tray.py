from sims4_sdk.save.tray import list_tray_households, read_household_binary, read_tray_library


def test_tray_varint_float_and_per_file_errors(tmp_path, monkeypatch):
    # FamilyData.family_account.sim.voice_pitch is encoded as a varint.
    sim = b"\x08\x01\x2a\x03Sam\x48\x02"
    family = b"\x1a\x04Test\x32" + bytes([len(sim)]) + sim
    payload = b"\x0a" + bytes([len(family)]) + family
    good = tmp_path / "good.householdbinary"
    good.write_bytes(bytes(16) + payload)
    (tmp_path / "bad.householdbinary").write_bytes(b"\xff")
    (tmp_path / "bad.trayitem").write_bytes(b"\xff")
    assert read_household_binary(good).sims[0].raw["voice_pitch"] == 2.0

    library = read_tray_library(tmp_path)
    assert [household.family_name for household in library.households] == ["Test"]
    assert {entry["path"] for entry in library.errors} == {
        str(tmp_path / "bad.householdbinary"), str(tmp_path / "bad.trayitem")
    }
    assert library.to_dict()["errors"] == library.errors

    # Unexpected per-file failures must not discard successfully read items.
    def fail(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("sims4_sdk.save.tray.read_tray_item", fail)
    assert any("RuntimeError: unexpected" in item["error"] for item in read_tray_library(tmp_path).errors)


def test_listing_keeps_partial_groups_and_ambiguous_images(tmp_path):
    sim = b"\x08\x01\x2a\x03Sam"
    family = b"\x1a\x04Test\x32" + bytes([len(sim)]) + sim
    payload = b"\x0a" + bytes([len(family)]) + family
    for key in ("0x10", "0x20"):
        (tmp_path / f"house!{key}.householdbinary").write_bytes(bytes(16) + payload)
    (tmp_path / "house!0x10.hhi").write_bytes(b"image")
    (tmp_path / "sim!0x1.sgi").write_bytes(b"image")
    (tmp_path / "orphan!0x30.trayitem").write_bytes(b"bad")

    listing = list_tray_households(tmp_path)
    groups = {group.identifier: group for group in listing.groups}
    assert groups["0x10"].household.sims[0].first_name == "Sam"
    assert groups["0x10"].household_images == [tmp_path / "house!0x10.hhi"]
    assert groups["0x30"].household is None
    assert listing.unmatched_images == [tmp_path / "sim!0x1.sgi"]
    assert len(listing.errors) == 2
    assert listing.to_dict()["groups"][0]["identifier"] in groups


def test_listing_does_not_select_duplicate_group_files(tmp_path):
    for prefix in ("a", "b"):
        (tmp_path / f"{prefix}!0x10.householdbinary").write_bytes(b"bad")
    listing = list_tray_households(tmp_path)
    assert len(listing.groups[0].household_files) == 2
    assert listing.groups[0].household is None
    assert len(listing.errors) == 2
