<#
.SYNOPSIS
Launch the Steam version of The Sims 4 in a disposable profile and wait for a Live Mode save.
.DESCRIPTION
Use the SDK-Live-smoke-test.package from the local startup automation build.
Launch from the signed-in game user's desktop. The test uses in-game callbacks
for Create a Sim and saving and briefly uses the foreground for lot placement.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$AutomationDirectory,
    [string]$Python = 'python',
    [string]$InstallDirectory = $env:SIMS4_INSTALL_DIR,
    [string]$UserDirectory = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Electronic Arts/The Sims 4'),
    [ValidateRange(1, 600)][int]$TimeoutSeconds = 90
)

$ErrorActionPreference = 'Stop'
$gameNames = @('TS4_x64', 'TS4_DX9_x64')
$launchNames = $gameNames + 'TS4_Launcher_x64'
$session = (Get-Process -Id $PID).SessionId
function Get-TestProcess {
    Get-Process -Name $launchNames -ErrorAction SilentlyContinue |
        Where-Object { $_.SessionId -eq $session -and -not $_.HasExited }
}

function Move-Profile([string]$Source, [string]$Destination) {
    $deadline = [Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        try {
            [IO.Directory]::Move($Source, $Destination)
            return
        } catch [IO.IOException] {
            if ($deadline.Elapsed.TotalSeconds -ge 5 -or (Test-Path -LiteralPath $Destination)) { throw }
            Start-Sleep -Milliseconds 100
        }
    }
}

$steamDirectory = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -Name SteamPath).SteamPath
$steam = Get-Item -LiteralPath (Join-Path $steamDirectory 'steam.exe')
if (-not $InstallDirectory) { throw 'Set SIMS4_INSTALL_DIR or pass -InstallDirectory.' }
$exe = Get-Item -LiteralPath (Join-Path $InstallDirectory 'Game/Bin/TS4_x64.exe')
if ($exe.VersionInfo.FileVersion -ne '1.129.39.1030') {
    throw "The UI automation targets game build 1.129.39.1030. Found $($exe.VersionInfo.FileVersion)."
}
$originalProfile = Get-Item -LiteralPath $UserDirectory
$defaultProfile = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Electronic Arts\The Sims 4'
if ($originalProfile.FullName -ne $defaultProfile -or -not $originalProfile.PSIsContainer -or
    ($originalProfile.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw "Run as the signed-in game user with a local profile at $defaultProfile."
}
if (Get-TestProcess) { throw 'Close The Sims 4 and its launcher before running the test.' }
$livePath = $originalProfile.FullName
$package = Get-Item -LiteralPath (Join-Path $AutomationDirectory 'SDK-Live-smoke-test.package')
$stamp = [guid]::NewGuid().ToString('N')
$backup = "$livePath.startup-original-$stamp"
$testProfile = "$livePath.startup-test-$stamp"
$log = Join-Path $package.DirectoryName "startup-$stamp.log"
$mods = New-Item -Path (Join-Path $testProfile 'Mods') -ItemType Directory
Copy-Item -LiteralPath $package.FullName -Destination $mods.FullName
& $Python (Join-Path $PSScriptRoot 'build_runtime.py') $exe.Directory.Parent.Parent.FullName $mods.FullName $log
if ($LASTEXITCODE -ne 0) { throw 'Could not compile the Live Mode hook.' }
Set-Content -LiteralPath (Join-Path $mods.FullName 'Resource.cfg') -Encoding ascii -Value @(
    'Priority 500', 'PackedFile *.package'
)

$options = Get-Content -LiteralPath (Join-Path $livePath 'Options.ini') -Raw
$settings = @{
    fullscreen = 0
    windowedfullscreen = 0
    modsdisabled = 0
    scriptmodsenabled = 1
    showmodliststartup = 0
    enableftuetutorialstart = 0
    tutorialenabled = 1
    guidanceenabled = 0
    guidanceautoenabled = 0
    packguidanceenabled = 0
}
foreach ($key in $settings.Keys) {
    $options = $options -replace "(?im)^\s*$key\s*=.*\r?\n?", ''
}
$options = $options -replace '(?im)^\[options\]\s*$', (
    "[options]`r`n" + (($settings.Keys | ForEach-Object { "$_ = $($settings[$_])" }) -join "`r`n")
)
Set-Content -LiteralPath (Join-Path $testProfile 'Options.ini') -Encoding ascii -Value $options
# Mark the two placement tips as seen while keeping the CAS Stories flow enabled.
Set-Content -LiteralPath (Join-Path $testProfile 'UserSetting.ini') -Encoding ascii -Value @(
    '[usersetting]',
    'tutorialtip_0x000000000004b641 = 1',
    'tutorialtip_0x000000000004b640 = 1',
    'guidancetip_0x000000000004bb77 = 1',
    'guidancetip_0x000000000004d836 = 1'
)

$activated = $false
$launched = $false
$saveName = $null
if (Get-TestProcess) { throw 'The Sims 4 started while the test profile was being prepared.' }
Move-Profile $livePath $backup
try {
    Move-Profile $testProfile $livePath
    $activated = $true
    $launched = $true
    Start-Process -FilePath $steam.FullName -ArgumentList '-applaunch','1222670','-w' -WindowStyle Hidden
    $clock = [Diagnostics.Stopwatch]::StartNew()
    $seenGame = $false
    $seenCasSave = $false
    $lastStamp = $null
    do {
        $game = Get-TestProcess | Where-Object ProcessName -in $gameNames
        if ($game) { $seenGame = $true }
        elseif ($seenGame) { throw 'The Sims 4 exited before creating a Live Mode save.' }

        $saves = Join-Path $livePath 'saves'
        if (-not $seenCasSave -and (Test-Path -LiteralPath (Join-Path $saves 'Slot_00000002.save'))) {
            $seenCasSave = $true
            Write-Verbose "CAS save appeared after $([int]$clock.Elapsed.TotalSeconds) seconds."
            $remaining = [Math]::Max(0, $TimeoutSeconds - $clock.Elapsed.TotalSeconds)
            & $Python (Join-Path $PSScriptRoot 'placement.py') $game.MainWindowHandle.ToInt64() $package.DirectoryName $saves $remaining
            if ($LASTEXITCODE -ne 0) { throw 'Could not select the starter lot.' }
        }
        $save = Get-Item -LiteralPath (Join-Path $saves 'Slot_0000007f.save') -ErrorAction SilentlyContinue
        if ($save -and $save.Length -gt 96) {
            $saveStamp = "$($save.Length):$($save.LastWriteTimeUtc.Ticks)"
            if ($saveStamp -eq $lastStamp) {
                try {
                    $stream = [IO.File]::Open($save.FullName, 'Open', 'Read', 'None')
                    try {
                        $header = New-Object byte[] 4
                        if ($stream.Read($header, 0, 4) -eq 4 -and
                            [Text.Encoding]::ASCII.GetString($header) -eq 'DBPF') {
                            $saveName = $save.Name
                            break
                        }
                    } finally { $stream.Dispose() }
                } catch [IO.IOException] { }
            }
            $lastStamp = $saveStamp
        } else {
            $lastStamp = $null
        }
        Start-Sleep -Milliseconds 250
    } while ($clock.Elapsed.TotalSeconds -lt $TimeoutSeconds)
    if (-not $saveName) {
        $stage = if ($seenCasSave) { 'world selection or lot entry' } else { 'launch or Create a Sim' }
        throw "Timed out at $stage after $TimeoutSeconds seconds. Test profile: $testProfile. Hook log: $log"
    }
} finally {
    if ($launched) {
        $running = @(Get-TestProcess)
        if ($running.Count) {
            $running | Stop-Process -Force -ErrorAction SilentlyContinue
            $running | Wait-Process -Timeout 15 -ErrorAction SilentlyContinue
        }
        if (Get-TestProcess) { throw "The game is still running. Original profile: $backup" }
    }
    try {
        if ($activated) { Move-Profile $livePath $testProfile }
        Move-Profile $backup $livePath
    } catch {
        throw "Could not restore the original profile from $backup. $($_.Exception.Message)"
    }
}
$result = Join-Path $testProfile "saves/$saveName"
$verified = & $Python (Join-Path $PSScriptRoot 'check_save.py') $result
if ($LASTEXITCODE -ne 0) { throw "The generated save failed validation. Save: $result" }
Write-Verbose $verified
$result
