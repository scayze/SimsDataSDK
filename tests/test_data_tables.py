import pytest

from sims4_sdk.core import DataTableError, DataTables, SimData, SimDataError


def test_rejects_non_data() -> None:
    with pytest.raises(DataTableError):
        DataTables.parse(b"STBL\x05\x00\x00")
    with pytest.raises(SimDataError):
        SimData.parse(b"STBL\x05\x00\x00")


def test_rejects_unknown_version() -> None:
    data = b"DATA" + (0x999).to_bytes(4, "little")
    with pytest.raises(DataTableError):
        DataTables.parse(data)


def test_truncated_raises() -> None:
    # A valid magic/version but nothing else.
    data = b"DATA" + (0x100).to_bytes(4, "little")
    with pytest.raises(DataTableError):
        DataTables.parse(data)
