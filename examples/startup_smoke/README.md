# Sims 4 startup smoke test

This Windows and Steam test starts a new game with a disposable profile. The UI automation randomizes one Sim, attempts to move the household into Crick Cabana, and requests a new save after the lot loads. The runner validates the resulting household with the SDK and prints the save path.

## Build once

Use game build `1.129.39.1030`, Java, JPEXS Free Flash Decompiler 26.5.0, and 64-bit Python with the SDK installed. Set `SIMS4_INSTALL_DIR` to the installation directory.

```powershell
python examples/startup_smoke/build_ui.py --ffdec C:/tools/ffdec/ffdec.jar --output .cache/startup-smoke
```

The build uses UI resources from your local installation. Keep the generated package in the ignored output directory.

## Run

Run from the signed-in Windows user's desktop with The Sims 4 closed and Steam and the EA app signed in.

```powershell
./examples/startup_smoke/run_startup_test.ps1 -AutomationDirectory .cache/startup-smoke -Verbose
```

The test starts windowed. Create a Sim and saving use in-game callbacks. World and lot selection use the foreground briefly and restore the previous window afterward. Keep the game on a visible monitor during this phase. Placement expects the base-game world grid at the default UI scale.

The runner polls for the save every 250 ms. Placement polls the visible game screen and clicks when the next screen is ready. `-TimeoutSeconds` bounds the overall wait.

The script temporarily renames the regular Sims profile and restores it after the game closes. Keep the PowerShell process running through cleanup. Each run preserves its separate profile and hook log for inspection. If cleanup reports a parked profile, close The Sims 4 and move the reported backup back to the regular profile path once that path is free.

## Check new-save overrides

Build the fixture at a new path, then pass it to the same runner. Use
`-ModPackage` to stage one or more extra packages in the disposable profile.

```powershell
$mod = python examples/startup_smoke/check_overrides.py build .cache/startup-smoke/new-save.package
$save = ./examples/startup_smoke/run_startup_test.ps1 -AutomationDirectory .cache/startup-smoke -ModPackage $mod -InspectSimTemplateId 469189 -TimeoutSeconds 155 -Verbose
$stamp = (Get-Item -LiteralPath $save).Directory.Parent.Name.Split('-')[-1]
python examples/startup_smoke/check_overrides.py check $save --log ".cache/startup-smoke/startup-$stamp.log"
```

The checker reads the generated save for BFF funds, Bella Goth's baked trait,
and Bella and Nancy Landgraab's starting friendship. The hook log verifies
Bella's loaded XML template separately.

## Check a starter household move

```powershell
$mod = python examples/startup_smoke/check_lot_move.py build .cache/startup-smoke/move-bff.package
$save = ./examples/startup_smoke/run_startup_test.ps1 -AutomationDirectory .cache/startup-smoke -ModPackage $mod -TimeoutSeconds 155 -Verbose
python examples/startup_smoke/check_lot_move.py check $save
```

The checker verifies the new home's zone and household references in both
directions and checks that the original lot is vacant.
