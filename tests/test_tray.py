from sims4_sdk.save.tray import read_household_binary, read_tray_library


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
