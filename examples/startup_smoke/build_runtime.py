"""Compile the startup test's Live Mode hook with the installed game Python."""

import argparse
import ctypes
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("install", type=Path)
    parser.add_argument("mods", type=Path)
    parser.add_argument("log", type=Path)
    parser.add_argument("sim_template_id", nargs="?", type=int, default=0)
    args = parser.parse_args()

    game = ctypes.CDLL(str(args.install / "Game/Bin/python37_x64.dll"))
    game.Py_SetPath.argtypes = [ctypes.c_wchar_p]
    game.Py_SetPath(str(args.install / "Data/Simulation/Gameplay/base.zip/lib"))
    game.PyRun_SimpleString.argtypes = [ctypes.c_char_p]
    game.Py_Initialize()
    try:
        hook = f"LOG_PATH = {str(args.log)!r}\nSIM_TEMPLATE_ID = {args.sim_template_id}\n"
        hook += Path(__file__).with_name("live_hook.py").read_text(encoding="utf-8")
        archive = args.mods / "SDK-Startup-Smoke.ts4script"
        if game.PyRun_SimpleString(f"""
from importlib.util import MAGIC_NUMBER
from marshal import dumps
from zipfile import ZipFile
with ZipFile({str(archive)!r}, 'w') as output:
    hook = compile({hook!r}, 'sdk_startup_smoke.py', 'exec')
    output.writestr('sdk_startup_smoke.pyc', MAGIC_NUMBER + bytes(12) + dumps(hook))
""".encode("utf-8")):
            raise SystemExit("Could not build the startup test's game script.")
    finally:
        game.Py_FinalizeEx()


if __name__ == "__main__":
    main()
