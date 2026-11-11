from pathlib import Path

from sims4_sdk.paths import (
    find_install_dir,
    find_user_dir,
    is_install_dir,
    is_user_dir,
    iter_pack_folders,
    iter_packages,
    iter_string_packages,
)
from sims4_sdk.installation import Installation


def _fake_install(root: Path) -> Path:
    (root / "Data" / "Simulation").mkdir(parents=True)
    (root / "Data" / "Simulation" / "SimulationFullBuild0.package").write_bytes(b"")
    (root / "Data" / "Simulation" / "SimulationDeltaBuild0.package").write_bytes(b"")
    (root / "Data" / "Client").mkdir(parents=True)
    (root / "Data" / "Client" / "Strings_ENG_US.package").write_bytes(b"")
    (root / "Delta" / "EP01").mkdir(parents=True)
    (root / "Delta" / "EP01" / "SimulationDeltaBuild0.package").write_bytes(b"")
    (root / "Delta" / "EP01" / "Strings_ENG_US.package").write_bytes(b"")
    (root / "Delta" / "notes").mkdir()
    return root


def test_install_detection(tmp_path: Path) -> None:
    install = _fake_install(tmp_path / "The Sims 4")
    assert is_install_dir(install)
    assert find_install_dir(explicit=install) == install
    assert not is_install_dir(tmp_path)


def test_user_detection(tmp_path: Path) -> None:
    user = tmp_path / "user"
    (user / "saves").mkdir(parents=True)
    assert is_user_dir(user)
    assert find_user_dir(explicit=user) == user


def test_iter_pack_folders_ignores_junk(tmp_path: Path) -> None:
    install = _fake_install(tmp_path / "The Sims 4")
    assert [p.name for p in iter_pack_folders(install)] == ["EP01"]


def test_iter_packages(tmp_path: Path) -> None:
    install = _fake_install(tmp_path / "The Sims 4")

    base = list(iter_packages(install, include_base=True))
    assert len(base) == 5  # 2 simulation + 1 client + 2 EP01 packages
    assert all(p.suffix == ".package" for p in base)

    delta_only = list(iter_packages(install, include_base=False))
    assert [p.parent.name for p in delta_only] == ["EP01", "EP01"]


def test_iter_string_packages(tmp_path: Path) -> None:
    install = _fake_install(tmp_path / "The Sims 4")
    strings = list(iter_string_packages(install, "ENG_US"))
    assert len(strings) == 2
    assert all(p.name == "Strings_ENG_US.package" for p in strings)


def test_installation_discovers_all_builds_and_pack_roots_before_deltas(tmp_path: Path) -> None:
    install = _fake_install(tmp_path / "The Sims 4")
    client = install / "Data" / "Client"
    for name in ("ClientFullBuild8.package", "ClientDeltaBuild8.package"):
        (client / name).write_bytes(b"")
    root_pack = install / "EP01"
    root_pack.mkdir()
    (root_pack / "ClientFullBuild0.package").write_bytes(b"")
    (root_pack / "Strings_ENG_US.package").write_bytes(b"")
    root_only = install / "SP99"
    root_only.mkdir()
    (root_only / "ClientFullBuild0.package").write_bytes(b"")
    user = tmp_path / "user"
    (user / "Mods").mkdir(parents=True)
    (user / "Mods" / "custom.package").write_bytes(b"")

    installation = Installation(install, user)
    packages = installation.packages
    paths = [info.path for info in packages]
    assert set(iter_packages(install)) == set(paths[:-1])
    assert client / "ClientFullBuild8.package" in paths
    assert client / "ClientDeltaBuild8.package" in paths
    assert paths.index(root_pack / "ClientFullBuild0.package") < paths.index(install / "Delta" / "EP01" / "SimulationDeltaBuild0.package")
    assert next(info for info in packages if info.path.parent == root_only).pack == "SP99"
    assert packages[-1].is_mod
    assert [info.path for info in installation.string_packages] == list(iter_string_packages(install)) + [packages[-1].path]
