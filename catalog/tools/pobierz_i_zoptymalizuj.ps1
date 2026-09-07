<#
    Pobiera modele producenta, rozpakowuje i przepuszcza przez optimize_model.py.

    Po co skrypt, a nie ręczna robota: pliki producentów są ciężkie (od kilku
    do dwustu megabajtów na jeden mebel) i prawie nigdy nie nadają się do
    przeglądarki bez redukcji. Przy dziesięciu meblach to dziesięć razy ta sama
    sekwencja: pobierz, rozpakuj, znajdź .dae, otwórz w Blenderze, zredukuj,
    wyeksportuj. Skrypt robi to jednym poleceniem i zapisuje log.

    Blender 5 nie czyta już Collady, dlatego wymuszamy 4.3.

    Uruchomienie z katalogu repozytorium:
        powershell -ExecutionPolicy Bypass -File catalog\tools\pobierz_i_zoptymalizuj.ps1
#>

param(
    [string]$Blender  = "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
    [string]$OutDir   = "catalog\models\comforty",
    [int]$Triangles   = 18000,
    [int]$Texture     = 1024,
    [int]$MaxZipMB    = 60,
    [string]$Log      = "work\pobieranie.log"
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

function Zapisz($tekst) {
    $linia = "{0}  {1}" -f (Get-Date -Format "HH:mm:ss"), $tekst
    Write-Output $linia
    Add-Content -Path $Log -Value $linia -Encoding UTF8
}

New-Item -ItemType Directory -Force -Path $OutDir, (Split-Path $Log -Parent) | Out-Null
$tmp = Join-Path $env:TEMP "room_modele"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

Zapisz "start; budzet trojkatow=$Triangles, tekstura=$Texture px, limit archiwum=$MaxZipMB MB"

$strona = Invoke-WebRequest -Uri "https://comforty.pl/downloads/" -UseBasicParsing -TimeoutSec 30
$linki = $strona.Links | Where-Object { $_.href -match '_dae\.zip$' } | Select-Object -ExpandProperty href -Unique
Zapisz "znaleziono archiwow DAE: $($linki.Count)"

foreach ($link in $linki) {
    $nazwa = (Split-Path $link -Leaf) -replace '_dae\.zip$', ''
    $url = "https://comforty.pl" + $link
    $zip = Join-Path $tmp ($nazwa + ".zip")
    $glb = Join-Path $OutDir ($nazwa + ".glb")

    if (Test-Path $glb) { Zapisz "$nazwa - juz zoptymalizowany, pomijam"; continue }

    try {
        $head = Invoke-WebRequest -Uri $url -Method Head -UseBasicParsing -TimeoutSec 20
        $mb = [math]::Round([int]$head.Headers['Content-Length'] / 1MB, 1)
    } catch { $mb = -1 }

    if ($mb -gt $MaxZipMB) {
        Zapisz "$nazwa - POMINIETY, archiwum $mb MB przekracza limit $MaxZipMB MB (podnies -MaxZipMB, jesli chcesz)"
        continue
    }

    if (-not (Test-Path $zip)) {
        Zapisz "$nazwa - pobieram ($mb MB)"
        try { Invoke-WebRequest -Uri $url -OutFile $zip -TimeoutSec 900 }
        catch { Zapisz "$nazwa - BLAD pobierania: $($_.Exception.Message)"; continue }
    }

    $rozpakowany = Join-Path $tmp $nazwa
    try { Expand-Archive -Path $zip -DestinationPath $rozpakowany -Force }
    catch { Zapisz "$nazwa - BLAD rozpakowania: $($_.Exception.Message)"; continue }

    $dae = Get-ChildItem $rozpakowany -Recurse -Filter *.dae |
           Sort-Object Length -Descending | Select-Object -First 1
    if (-not $dae) { Zapisz "$nazwa - brak pliku .dae w archiwum"; continue }

    Zapisz "$nazwa - optymalizuje $($dae.Name) ($([math]::Round($dae.Length/1MB,1)) MB)"
    $wynik = & $Blender --background --python-exit-code 1 --python "catalog\tools\optimize_model.py" -- `
        --in $dae.FullName --out $glb --triangles $Triangles --texture $Texture 2>&1

    $podsumowanie = $wynik | Select-String -Pattern "Trojkaty|Plik wynikowy|Gabaryt" 
    foreach ($p in $podsumowanie) { Zapisz "  $($p.ToString().Trim())" }

    if (Test-Path $glb) {
        Zapisz "$nazwa - GOTOWE, $([math]::Round((Get-Item $glb).Length/1KB,0)) kB"
    } else {
        Zapisz "$nazwa - BLAD optymalizacji"
    }
}

Zapisz "koniec"
