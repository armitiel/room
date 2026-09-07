# Integracja Unreal

Projekt `RoomDemo` powstaje z tego samego źródła co wersja przeglądarkowa:
`datasets/sample/kruszczyki-22/scene.json`. Geometria idzie przez Blendera do
FBX, a poziom w Unrealu buduje skrypt — nie ma kroku „ktoś kliknął import".

## Jedna komenda

```powershell
powershell -ExecutionPolicy Bypass -File unreal\tools\build_unreal.ps1
```

Krok 1 (`blender/scripts/export_unreal.py`) zapisuje `work/unreal/room.fbx`
i manifest `work/unreal/room-manifest.json`. Krok 2 uruchamia silnik bezgłowo
i wykonuje `unreal/tools/import_scene.py`. Wynik: poziom
`/Game/Room/Maps/L_Room` i raport `work/unreal/unreal-report.json`.

`-SkipExport` pomija Blendera, gdy FBX już jest.

## Co robi manifest

Unreal nazywa zasoby po nazwach węzłów FBX, a te po oczyszczeniu nie są
unikalne (`chair(Clone).001`, polskie znaki, kropki). Dlatego eksport nadaje
każdej siatce krótki identyfikator (`S0000`, `F0123`) i zapisuje obok, czym
ona jest: rola, pomieszczenie, mebel, produkt, transformacja i bryła
w metrach. Importer czyta manifest i niczego nie zgaduje z nazw.

Pierwsze podejście bez manifestu dało 241 zasobów zamiast 246 — pięć siatek
nadpisało się nawzajem pod nazwami `Null` i `NONE_005`. Nikt by tego nie
zauważył na oko.

## Układy współrzędnych

Przejście Blender → Unreal to odbicie względem płaszczyzny XZ oraz metry na
centymetry:

| wielkość | przeliczenie |
|---|---|
| położenie | `(x, y, z) → (100x, -100y, 100z)` |
| obrót (kwaternion) | `(w, x, y, z) → (w, -x, y, -z)` |
| skala | bez zmian |

Odbicie odwraca skrętność, dlatego zwrot obrotu zmienia znak. Zamiast wierzyć
temu wyprowadzeniu, importer porównuje bryłę **każdego** obiektu z bryłą
policzoną w Blenderze. Ostatni pomiar: 246 obiektów, największa różnica
**0,04 cm**, bryła całej sceny **0,00 cm**.

## Sprawdzone zachowania silnika 5.8.2

To nie są przypuszczenia z dokumentacji, tylko wynik prób w tej instalacji.

- FBX obsługuje **Interchange**, nie stary importer. Ustawienia `FbxImportUI`
  są tłumaczone, ale `import_uniform_scale` jest ignorowane.
- `transform_vertex_to_absolute=True` daje siatki we współrzędnych sceny, więc
  bryła każdej z nich obejmuje cały dom. Silnik liczy wtedy pole odległości
  w maksymalnej rozdzielczości dla każdego obiektu — mierzone 15–22 s na
  obiekt, czyli ponad godzina dla tej sceny, i do tego znika odcinanie widoku.
  Dlatego import jest lokalny, a pozycje pochodzą z manifestu.
- `spawn_actor_from_object` w komandlecie zwraca `None`
  („SpawnActorFromObject. No actor was spawned"). Aktorów stawiamy z klasy
  i sami podpinamy siatkę.
- `get_capturable_properties` przyjmuje jeden argument (aktora), nie dwa.
  Właściwość materiału to `Static Mesh Component / Material[0]`; na liście jest
  też `Material Cache Tile Count`, które nie jest materiałem.
- `StaticMeshEditorSubsystem` nie istnieje w komandlecie, a
  `EditorStaticMeshLibrary.set_lod_build_settings` przyjmuje Build Scale bez
  błędu i **nie zmienia geometrii**. Skrypt to mierzy, cofa ustawienie
  i przelicza metry na centymetry skalą aktora. Skutek uboczny: aktorzy mają
  Scale rzędu setek. Scena jest poprawna, pole w edytorze wygląda dziwnie.
- `new_level` tworzy i od razu zapisuje zasób, więc przy drugim przebiegu
  zwraca `False`. Skrypt otwiera wtedy istniejący poziom i czyści go.

## Pułapka poza silnikiem

`Build.bat` składa ścieżkę pliku blokady z `%TMP%`. Gdy `TMP` nie jest
ustawione — tak bywa w sesjach zdalnych — ścieżka wychodzi na katalog główny
dysku, pliku nie da się utworzyć i silnik **w nieskończoność** czeka na
zwolnienie blokady, bez żadnego komunikatu w logu. `build_unreal.ps1` ustawia
`TMP`, jeśli go brakuje.

## Warianty

`LVS_Wykonczenie` to `LevelVariantSets` z jednym zestawem `Wykonczenie`
i wariantami o **tych samych identyfikatorach co w przeglądarce**: `basic`
i `premium`. Przypisania wykończeń liczy ta sama reguła co `resolveFinish()`
w `web/index.html`: pasuje rola, `room_id` zgadza się albo go nie ma, wygrywa
ostatnie przypisanie.

W poziomie stoi `LevelVariantSetsActor`. Przełączenie z kodu:

```
Actor->SwitchOnVariantByName("Wykonczenie", "premium");
```

to odpowiednik `RoomViewer.setVariant('premium')` w przeglądarce.

## Czego jeszcze nie ma

- **Materiały to płaski kolor plus szorstkość.** Przeglądarka rysuje jeszcze
  wzór (deski, płytki, tynk) proceduralnie; w Unrealu tego nie ma.
- **Pionek lata, nie chodzi.** `GameModeBase` daje `DefaultPawn`: kolizje ze
  ścianami działają, grawitacji nie ma. Chodzenie wymaga postaci z Blueprintem.
- **Światło jest orientacyjne.** Słońce, niebo, atmosfera i jedna lampa na
  pomieszczenie liczona ze środka ciężkości wielokąta. To nie jest scenografia.
- **Pixel Streaming nie istnieje.** Ani buildu serwerowego, ani hostingu.
- Scena źródłowa ma status `draft`; cztery pomieszczenia czekają na
  potwierdzenie wymiarów, a modele Comforty na ustalenie praw.

## Co jest w repozytorium

Tylko źródła: `RoomDemo.uproject`, `Config/` i skrypty. Katalogi `Content`,
`Saved`, `Intermediate` i `DerivedDataCache` powstają z FBX i `scene.json`,
więc `.gitignore` je pomija. Poziom odtwarza się jedną komendą.
