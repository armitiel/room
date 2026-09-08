<#
    Kadry z poziomu Room: jeden plik PNG na wariant i widok.

    Edytor startuje z prawdziwa grafika (bez -nullrhi), bo zdjecie ma przejsc
    przez pelny post-process. Skrypt pythona sam zamyka edytor, kiedy skonczy,
    wiec ta komenda po prostu czeka.

    Przyklad:
        powershell -ExecutionPolicy Bypass -File unreal\tools\render_shots.ps1
        powershell -ExecutionPolicy Bypass -File unreal\tools\render_shots.ps1 -Res 3840x2160
#>
param(
    [string]$Scene   = "datasets\pokoj-poddasze\scene.json",
    [string]$Renders = "work\renders",
    [string]$Res     = "2560x1440",
    [string]$Engine  = "C:\Program Files\Epic Games\UE_5.8"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root

if (-not $env:TMP) { $env:TMP = $env:TEMP }
New-Item -ItemType Directory -Force -Path $Renders | Out-Null

$env:ROOM_SCENE    = (Resolve-Path $Scene).Path
$env:ROOM_RENDERS  = (Resolve-Path $Renders).Path
$env:ROOM_SHOT_RES = $Res

$exe = Join-Path $Engine "Engine\Binaries\Win64\UnrealEditor.exe"
if (-not (Test-Path $exe)) { throw "Nie znaleziono edytora: $exe" }
$projekt = Join-Path $root "unreal\RoomDemo\RoomDemo.uproject"
$skrypt  = (Join-Path $root "unreal\tools\render_shots.py") -replace '\\', '/'

# Dwie proby wczesniej poszly w kosz, wiec komenda idzie przez plik .cmd:
# - "-ExecCmds=py <sciezka>" bez cudzyslowu rozpada sie na spacji i silnik
#   wykonuje samo "py";
# - "-ExecutePythonScript=" wykonuje skrypt i NATYCHMIAST zamyka edytor,
#   a nasz skrypt tylko rejestruje petle po ticku i wraca - edytor gasl,
#   zanim zrobil pierwsza klatke.
# W pliku .cmd mamy pelna kontrole nad cudzyslowami, czego Start-Process nie
# daje.
$plikCmd = Join-Path $root "work\unreal\render-uruchom.cmd"
@(
    '@echo off',
    ('"' + $exe + '" "' + $projekt + '" /Game/Room/Maps/L_Room ' +
     '-ExecCmds="py ' + $skrypt + '" -nosplash')
) | Set-Content -Path $plikCmd -Encoding ASCII

# Ile kadrow: kazdy wariant razy kazdy widok z presentation.views.
$scena = Get-Content $env:ROOM_SCENE -Raw | ConvertFrom-Json
$liczbaWidokow = ($scena.presentation.views | Get-Member -MemberType NoteProperty).Count
$liczbaWariantow = [Math]::Max(1, $scena.variants.Count)
$ile = $liczbaWidokow * $liczbaWariantow

$raport = Join-Path $env:ROOM_RENDERS "render-report.json"
Remove-Item $raport -ErrorAction SilentlyContinue

# Jeden kadr na uruchomienie edytora - patrz komentarz w render_shots.py.
for ($i = 0; $i -lt $ile; $i++) {
    Write-Host "Kadr $($i + 1) z $ile ($Res)"
    $env:ROOM_SHOT_INDEX = "$i"
    $proces = Start-Process -FilePath $plikCmd -PassThru -WindowStyle Hidden
    $proces.WaitForExit()
}

if (-not (Test-Path $raport)) { throw "Brak raportu: $raport" }
$dane = Get-Content $raport -Raw | ConvertFrom-Json
$dane.kadry | ForEach-Object { Write-Host " - $($_.wariant) / $($_.widok): $($_.plik)" }
Write-Host "Gotowe: $($dane.kadry.Count) kadrow w $env:ROOM_RENDERS"
