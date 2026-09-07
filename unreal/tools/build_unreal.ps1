<#
    Jedna komenda: scena z Blendera -> poziom w Unrealu.

    Krok 1 eksportuje FBX i manifest, krok 2 uruchamia silnik bezglowo i
    buduje poziom. Oba kroki loguja do work\unreal.
    Bez polskich znakow: Windows PowerShell czyta .ps1 w kodowaniu ANSI.

    Domyslnie buduje pokoj na poddaszu (rekonstrukcja ze zdjec).

    Przyklad:
        powershell -ExecutionPolicy Bypass -File unreal\tools\build_unreal.ps1

    Mieszkanie demo:
        powershell -ExecutionPolicy Bypass -File unreal\tools\build_unreal.ps1 `
            -Blend work\scenes\showcase\main.blend `
            -Scene datasets\sample\kruszczyki-22\scene.json -Roles ""
#>
param(
    [string]$Blend   = "work\scenes\attic-room-v06\Room-attic-v06.blend",
    [string]$Scene   = "datasets\pokoj-poddasze\scene.json",
    [string]$Roles   = "datasets\pokoj-poddasze\role-map.json",
    [string]$Textures = "work\textures",
    [string]$Blender = "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
    [string]$Engine  = "C:\Program Files\Epic Games\UE_5.8",
    [switch]$SkipExport
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root

# Build.bat silnika sklada sciezke pliku blokady z %TMP%. Gdy TMP nie jest
# ustawione (tak bywa w sesjach zdalnych), sciezka wychodzi na katalog glowny
# dysku, utworzenie pliku sie nie udaje i silnik w nieskonczonosc czeka na
# zwolnienie blokady. To kosztowalo godzine - dlatego ta linia jest tutaj.
if (-not $env:TMP) { $env:TMP = $env:TEMP }
if (-not $env:TMP) { $env:TMP = Join-Path $env:USERPROFILE "AppData\Local\Temp" }

$work = Join-Path $root "work\unreal"
New-Item -ItemType Directory -Force -Path $work | Out-Null
$fbx      = Join-Path $work "room.fbx"
$manifest = Join-Path $work "room-manifest.json"
$report   = Join-Path $work "unreal-report.json"
$project  = Join-Path $root "unreal\RoomDemo\RoomDemo.uproject"

if (-not $SkipExport) {
    if (-not (Test-Path $Blender)) { throw "Nie znaleziono Blendera: $Blender" }
    if (-not (Test-Path $Blend))   { throw "Nie znaleziono pliku sceny: $Blend" }
    # Mapa rol jest potrzebna scenom, ktore nie przeszly przez build_scene.py
    # i nie maja wlasciwosci role/room_id na obiektach. Pusty -Roles wylacza ja.
    $mapa = @()
    if ($Roles) {
        if (-not (Test-Path $Roles)) { throw "Nie znaleziono mapy rol: $Roles" }
        $mapa = @("--roles", (Resolve-Path $Roles).Path)
    }
    Write-Host "1/2 Eksport FBX i manifestu z $Blend"
    & $Blender --background --factory-startup $Blend --python-exit-code 1 `
        --python "blender\scripts\export_unreal.py" -- `
        --fbx $fbx --manifest $manifest @mapa 2>&1 |
        Tee-Object -FilePath (Join-Path $work "export.log") | Select-Object -Last 5
    if ($LASTEXITCODE -ne 0) { throw "Eksport z Blendera zwrocil kod $LASTEXITCODE" }
}
if (-not (Test-Path $manifest)) { throw "Brak manifestu: $manifest" }

$cmd = Join-Path $Engine "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
if (-not (Test-Path $cmd)) { throw "Nie znaleziono silnika: $cmd" }

$env:ROOM_MANIFEST = $manifest
$env:ROOM_SCENE    = (Resolve-Path $Scene).Path
$env:ROOM_REPORT   = $report
# Tekstury dobrane osobno (CC0). Leza poza projektem, wiec importer wciaga je
# przy kazdej budowie; brak katalogu nie jest bledem.
$env:ROOM_TEXTURES = if (Test-Path $Textures) { (Resolve-Path $Textures).Path } else { "" }
Remove-Item $report -ErrorAction SilentlyContinue

Write-Host "2/2 Budowa poziomu w Unrealu (to trwa kilka minut)"
$log = Join-Path $work "unreal.log"
$script = (Join-Path $root "unreal\tools\import_scene.py") -replace '\\', '/'
$process = Start-Process -FilePath $cmd -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $log `
    -ArgumentList @("`"$project`"", "-run=pythonscript", "-script=`"$script`"",
                    "-unattended", "-nopause", "-nosplash", "-nullrhi", "-stdout")
$process.WaitForExit()

if (-not (Test-Path $report)) {
    Write-Host "Brak raportu. Ostatnie linie logu:"
    Get-Content $log -Tail 40
    throw "Budowa poziomu sie nie powiodla; pelny log: $log"
}
$data = Get-Content $report -Raw | ConvertFrom-Json
$data.steps | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 4 }
if ($data.notes.Count -gt 0) {
    Write-Host ""
    Write-Host "Uwagi:"
    $data.notes | ForEach-Object { Write-Host " - $_" }
}
if ($data.problems.Count -gt 0) {
    Write-Host ""
    Write-Host "Problemy:" -ForegroundColor Yellow
    $data.problems | ForEach-Object { Write-Host " - $_" -ForegroundColor Yellow }
    exit 1
}
Write-Host ""
Write-Host "Gotowe. Poziom: /Game/Room/Maps/L_Room. Raport: $report"
