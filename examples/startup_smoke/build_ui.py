"""Build the startup test's UI package from the local Sims 4 installation."""

import argparse
import os
from pathlib import Path
import re
import struct
import subprocess

from sims4_sdk.core.dbpf import DBPF, ResourceKey


FLAG = "Sims4SdkCasSmokeTest"
SCOPE = "sdk-phase-one"
PLAY = "Sims4SdkCasSmokePlay"
UI_SETTINGS = 'getlex QName(PackageNamespace("olympus.core"),"UISettings")'
COMM = 'getlex QName(PackageNamespace("olympus.io"),"CommunicationManager")'
TIMER = 'QName(PackageNamespace("flash.utils"),"setTimeout")'


def public(name):
    return f'QName(PackageNamespace(""),"{name}")'


def protected(class_name, name):
    package, cls = class_name.rsplit(".", 1)
    return f'QName(ProtectedNamespace("{package}:{cls}"),"{name}")'


def session_settings():
    return [UI_SETTINGS, f'getproperty {public("SessionSettings")}', f'pushstring "{FLAG}"']


def check_flag(label):
    return [*session_settings(), f'pushstring "{SCOPE}"',
            f'callproperty {public("GetValue")}, 2', f"iffalse {label}"]


def delayed_method(class_name, method, millis, pass_null=False):
    return [
        f"findpropstrict {TIMER}", "getlocal0", f"getproperty {protected(class_name, method)}",
        f"pushshort {millis}", *(["pushnull"] if pass_null else []),
        f"callpropvoid {TIMER}, {3 if pass_null else 2}",
    ]


def patch_method(asset, cls, method_name, instructions, *, at_entry=False):
    helper = cls.rsplit(".", 1)[-1]
    asm_path, = (GFX / f"pcode-{asset}").rglob(f"{helper}.pcode")
    source_path, = (GFX / f"ids-{asset}").rglob(f"{helper}.as")
    function = rf"\bfunction {re.escape(method_name)}\("
    source = re.search(function + r"[^\n]*\n\s*\{\s*// method body index: (\d+)",
                       source_path.read_text(encoding="utf-8"))
    asm = re.search(function + r"[^\n]*\n[\s\S]*?^\s*method\s*\n([\s\S]*?)^\s*end ; method",
                    asm_path.read_text(encoding="utf-8"), re.MULTILINE)
    if source is None or asm is None:
        raise ValueError(f"missing method {cls}.{method_name}")
    lines = [line.strip() for line in asm[1].splitlines()]
    if at_entry:
        start = lines.index("code")
        if lines[start + 1:start + 3] != ["getlocal0", "pushscope"]:
            raise ValueError(f"unexpected method prologue in {method_name}")
        insertion = start + 3
    else:
        insertion = max(i for i, line in enumerate(lines) if line == "returnvoid")
    lines[insertion:insertion] = instructions
    stack = next(i for i, line in enumerate(lines) if line.startswith("maxstack "))
    lines[stack] = f"maxstack {max(int(lines[stack].split()[1]), 12)}"
    output = GFX / f"{helper}-{method_name}.pcode"
    output.write_text("method\n" + "\n".join(lines) + "\nend ; method\n", encoding="utf-8")
    return [cls, str(output), source[1]]


def assemble(asset, cls, edits):
    command = ["java", "-Djava.awt.headless=true", f"-Duser.home={ROOT}",
               "-jar", str(FFDEC)]
    original = GFX / f"{asset}.gfx"
    patched = GFX / f"{asset}-patched.gfx"
    export = [*command, "-selectclass", cls]
    subprocess.run([*export, "-config", "showMethodBodyId=true", "-export", "script",
                    str(GFX / f"ids-{asset}"), str(original)], cwd=ROOT, check=True)
    subprocess.run([*export, "-format", "script:pcode", "-export", "script",
                    str(GFX / f"pcode-{asset}"), str(original)], cwd=ROOT, check=True)
    args = []
    for method, instructions, at_entry in edits:
        args.extend(patch_method(asset, cls, method, instructions, at_entry=at_entry))
    subprocess.run([*command, "-replace", str(original), str(patched), *args], cwd=ROOT, check=True)
    return patched.read_bytes()


def write_package(resources, filename):
    header = bytearray(96)
    header[:4] = b"DBPF"
    struct.pack_into("<II", header, 4, 2, 1)
    index_size = 4 + 32 * len(resources)
    struct.pack_into("<I", header, 0x24, len(resources))
    struct.pack_into("<I", header, 0x2C, index_size)
    struct.pack_into("<II", header, 0x3C, 3, 96)
    index = bytearray(4)
    offset = len(header) + index_size
    for key, data in resources:
        if not data.startswith((b"GFX", b"CFX")):
            raise ValueError(f"patch produced an unexpected resource format for {key}")
        size = len(data)
        index.extend(struct.pack("<IIIIIIIHH", key.type_id, key.group, key.instance >> 32,
                                 key.instance & 0xffffffff, offset, size | 0x80000000,
                                 size, 0, 1))
        offset += size
    output = ROOT / filename
    output.write_bytes(header + index + b"".join(data for _, data in resources))
    with DBPF(output) as parsed:
        assert len(parsed.entries) == len(resources)
        assert all(parsed.read_resource(key) == data for key, data in resources)
    print(output, flush=True)


def main():
    global ROOT, GFX, FFDEC
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", type=Path, default=os.environ.get("SIMS4_INSTALL_DIR"), required="SIMS4_INSTALL_DIR" not in os.environ)
    parser.add_argument("--ffdec", type=Path, required=True, help="Path to ffdec.jar")
    parser.add_argument("--output", type=Path, required=True)
    settings = parser.parse_args()
    ROOT = settings.output.resolve()
    GFX = ROOT / "gfx"
    GFX.mkdir(parents=True, exist_ok=True)
    FFDEC = settings.ffdec.resolve(strict=True)
    assets = {
        "gameentrylauncher": 0x6D20AB71641B1539,
        "widgets_CAS_Stories_CASStoriesMain": 0xD587E4F081BD12EF,
        "CASNavigation": 0x17ABC8CF056C8442,
        "CASHouseholdSummary": 0x46B5617B3F773461,
    }
    with DBPF(settings.install / "Data/Client/UI.package") as package:
        for name, instance in assets.items():
            (GFX / f"{name}.gfx").write_bytes(package.read_resource(ResourceKey(0x62ECC59A, 0, instance)))
    launcher = "widgets.GameEntry.Launcher.controls.LauncherNavigation"
    stories = "widgets.CAS.Stories.CASStoriesMain"
    nav = "widgets.CAS.Navigation.CASNavigationMain"
    summary = "widgets.CAS.HouseholdSummary.CASHouseholdSummaryMain"
    resources = []
    launcher_data = assemble("gameentrylauncher", launcher, [("ConfigUI", [
        "getlocal1", "iffalse smoke_launcher_end",
        *session_settings(), "pushtrue", f'pushstring "{SCOPE}"',
        f'callpropvoid {public("SetValue")}, 3',
        # The game can ignore the transition while the main menu is loading.
        *delayed_method(launcher, "GotoNewGame", 8000), "smoke_launcher_end:",
    ], False)])
    resources.append((ResourceKey(0x62ECC59A, 0, 0x6D20AB71641B1539), launcher_data))
    stories_data = assemble("widgets_CAS_Stories_CASStoriesMain", stories, [
        ("StartFlow", [*check_flag("smoke_story_original"), "getlocal0", "pushbyte 1",
         f'callpropvoid {protected(stories, "MyStoryDialogResult")}, 1',
         *delayed_method(stories, "RandomizeSim", 1800), "returnvoid", "smoke_story_original:"], True),
        ("RandomizeSim", [*check_flag("smoke_randomize_end"), f"findpropstrict {TIMER}", COMM,
         f'getproperty {public("SendUIMessage")}', "pushshort 2500", f'pushstring "{PLAY}"',
         "pushnull", f"callpropvoid {TIMER}, 4", "smoke_randomize_end:"], False),
    ])
    resources.append((ResourceKey(0x62ECC59A, 0, 0xD587E4F081BD12EF), stories_data))
    nav_data = assemble("CASNavigation", nav, [("Initialize", [
        *check_flag("smoke_nav_end"), "getlocal0", f'pushstring "{PLAY}"', "getlocal0",
        f'getproperty {protected(nav, "OnPlayButtonClicked")}',
        f'callpropvoid {public("AddMessageListener")}, 2', "smoke_nav_end:",
    ], False)])
    resources.append((ResourceKey(0x62ECC59A, 0, 0x17ABC8CF056C8442), nav_data))
    summary_data = assemble("CASHouseholdSummary", summary, [("Show", [
        *check_flag("smoke_summary_end"), *delayed_method(summary, "OnDoneClick", 250, True),
        "smoke_summary_end:",
    ], False)])
    resources.append((ResourceKey(0x62ECC59A, 0, 0x46B5617B3F773461), summary_data))
    write_package(resources, "SDK-Live-smoke-test.package")


if __name__ == "__main__":
    main()
