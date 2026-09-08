# Integracja Unreal

Poziom `/Game/Room/Maps/L_Room` to **pokój na poddaszu** — rekonstrukcja ze
zdjęć z `work/scenes/attic-room-v06/Room-attic-v06.blend`, opisana kontraktem
`datasets/pokoj-poddasze/scene.json`. Geometria idzie przez Blendera do FBX,
a poziom buduje skrypt — nie ma kroku „ktoś kliknął import".

Mieszkanie demo (Kruszczyki 22) nie zniknęło, tylko nie jest już domyślne:
buduje się tą samą komendą z innymi parametrami. Poziom jest jeden, więc
budowa drugiej sceny nadpisuje pierwszą.

## Jedna komenda

```powershell
powershell -ExecutionPolicy Bypass -File unreal\tools\build_unreal.ps1
```

Mieszkanie demo:

```powershell
powershell -ExecutionPolicy Bypass -File unreal\tools\build_unreal.ps1 `
    -Blend work\scenes\showcase\main.blend `
    -Scene datasets\sample\kruszczyki-22\scene.json -Roles ""
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

Import zaczyna od skasowania `/Game/Room/Meshes`. Bez tego siatki poprzedniej
sceny zostają w projekcie: budowa pokoju (242 obiekty) po mieszkaniu (246)
zostawiłaby cztery sieroty, a dopasowanie po początku nazwy mogłoby je komuś
podstawić. Ostatnia budowa skasowała 380 zasobów po mieszkaniu.

## Mapa ról

Blend z rekonstrukcji nie przeszedł przez `build_scene.py`, więc jego obiekty
nie mają właściwości `role` ani `room_id` — mają za to sensowne nazwy. Rolę
nadaje im `datasets/pokoj-poddasze/role-map.json`, podawany eksporterowi przez
`--roles`. Wygrywa **najdłuższy** pasujący prefiks, dzięki czemu `High wall
skirting` idzie do listwy, a nie do ściany. Co nie pasuje do żadnej reguły,
zostaje meblem i zachowuje własny materiał: grzejnik, gniazda, łóżko i lampy
nie zmieniają się z wariantem.

Wynik dla pokoju: podłoga 77, meble 122, ściany 13, sufit 9, stolarka okienna
9, listwy 4, stolarka drzwiowa 3, szyby 3, skrzydło 2. Razem 242 siatki,
z czego 120 to powierzchnie przełączane wariantem.

`skirting` doszło przy tej okazji do listy powierzchni w obu skryptach —
listwa ma własne gniazdo materiałowe w kontrakcie wariantów, więc nie ma
powodu, żeby w Unrealu była meblem.

## Materiały: tekstura rzutowana ze świata

Dwadzieścia ścian, skosów i ościeżnic w tej scenie **nie ma współrzędnych
UV** — to płaszczyzny wycięte skryptem, nikt ich nie rozwijał. Zamiast
dorabiać im UV, `M_RoomSurface` bierze teksturę przez `WorldAlignedTexture`:
rzut z trzech osi świata, a rozmiar podaje się w centymetrach. Dzięki temu
`scale_m` w wykończeniu znaczy dokładnie to, co format produktu w katalogu —
„deska co 1,44 m" to osiem desek po 18 cm, czyli tyle, ile ma deska w scenie.

Wykończenie w `scene.json` może nieść `texture` (nazwa zasobu), `tint`
(barwienie tekstury, bo mnożenie potrafi tylko przyciemnić) i `normal`.
Bez `texture` w gnieździe siedzi biała tekstura i zostaje czysty kolor —
czyli zachowanie sprzed tej zmiany.

**Kierunek tekstury.** W plikach z ambientCG deski leżą poziomo, a w pokoju
biegną wzdłuż osi Y — wychodziły w poprzek prawdziwych desek. Rzut ze świata
nie ma wejścia na obrót, więc obraca się sam plik:
`work/unreal/obroc_deski.py` zapisuje wersje `...rot_...`. Mapa normalnych
przy obrocie dostaje zamianę kanałów (`nowe R = 255 − G`, `nowe G = R`), bo
R i G to składowe wektora w płaszczyźnie tekstury i muszą obrócić się razem
z pikselami.

**Czego tu nie ma:** map normalnych na powierzchniach. Silnik 5.8 nie ma
`WorldAlignedNormal` (w katalogu `Texturing` są tylko `ScaleUVsByCenter`,
`TextureCropping` i `WorldAlignedTexture`), a podstawienie zwykłej funkcji
nie przejdzie — sampler w niej jest kolorowy, mapa normalnych ma inny typ
i materiał się nie skompiluje. Żeby mieć mikrorelief, trzeba albo napisać
własną funkcję materiałową, albo rozwinąć UV w Blenderze. Pliki `_Normal`
są już pobrane i zaimportowane, czekają.

## Skąd biorą się tekstury

Dwa źródła. **Z blenda** — obrazki spakowane w pliku wychodzą razem z FBX
(`path_mode="COPY"`, `embed_textures=True` w eksporterze) i lądują na
meblach: splot tapicerki, prążek pościeli, orzech na frontach. Bez tych
dwóch linii FBX szedł bez ani jednej tekstury i wszystko było płaskim
kolorem. **Z ambientCG** (CC0) — `work/unreal/pobierz_tekstury.py` ściąga
kolor, normalne i szorstkość w 1K do `work/textures`, a importer wciąga ten
katalog przy każdej budowie. `work/` jest poza repozytorium, więc na nowej
maszynie trzeba je pobrać ponownie tym skryptem.

## Fazowanie krawędzi

Eksporter dokłada każdej bryle fazkę 2,5 mm (modyfikator Bevel, 2 segmenty,
limit kąta 30°, clamp overlap) i zdejmuje ją zaraz po zapisaniu FBX.
**Plik .blend zostaje nietknięty** — jest otwierany tylko do odczytu.
Bez fazki każde pudełko czyta się jak karton, bo matematycznie ostra
krawędź nie ma czym złapać światła. Clamp overlap pilnuje drobiazgów:
śrubka 6 mm dostaje fazkę mniejszą, zamiast zwinąć się w kulę.
Wyłącznik: `--no-bevel`.

## Światło

Wszystko jest dynamiczne (Lumen), nic się nie zapieka.

- **Słońce** 11 lx, 6200 K, `light_source_angle` 1,5° — prawdziwe słońce ma
  na niebie około pół stopnia i dlatego jego cień ma miękką krawędź. Przy
  domyślnym punkcie cienie były wycięte nożem.
- **Niebo** z podglądem w czasie rzeczywistym, dolna półkula **nie czarna** —
  to ono rozjaśnia cienie. Przy czarnej półkuli wszystko, na co nie pada
  słońce, było czarne.
- **Lampa w pomieszczeniu** 600 lm, 3800 K, źródło o realnym rozmiarze
  (miękki cień), 60 cm pod sufitem. Przy 35 cm świeciła w spody szyn
  opraw i te rzucały na sufit wielkie ciemne plamy.
- **Światło okna** — prostokąt w świetle każdego otworu z `openings`,
  odsunięty 25 cm na zewnątrz, skierowany do środka, 900 lm, 7000 K.
  Odpowiada temu, że przez szybę świeci całe niebo, a nie tylko wąski snop
  słońca. Nikt go nie ustawia ręcznie — okno dopisane w kontrakcie od razu
  dostaje swoje światło.
- **Ekspozycja** automatyczna z histogramu, bez przesunięcia, plus jakość
  Lumen podniesiona w PostProcessVolume.

Ciepłota barw ma znaczenie: przy 5600 K słońca wnętrze z brązową podłogą
wychodziło pomarańczowe, bo ciepłe światło odbija się od ciepłej podłogi
i barwa mnoży się sama przez siebie.

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
policzoną w Blenderze. Ostatni pomiar (pokój, 7 września 2026): 242 obiekty,
największa różnica **0,01 cm** — i to na deskach podłogowych o grubości
12 mm. Wcześniejszy pomiar na mieszkaniu: 246 obiektów, 0,04 cm.

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

W pokoju `basic` to **stan obecny** — kolory odczytane z rekonstrukcji:
brązowa podłoga, chłodny szary tynk, orzechowe listwy i stolarka. `premium`
to propozycja jasnego wykończenia, a nie coś, co w pokoju stoi. Ostatnia
budowa: 120 powierzchni w każdym wariancie, wszystkie 120 różnią się między
wariantami.

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
- **Blend pokoju jest poza repozytorium.** `work/` jest w `.gitignore`, więc
  na nowej maszynie trzeba mieć `Room-attic-v06.blend` albo odtworzyć go
  skryptami `reconstruct_attic*.py` i `refine_*_v0*.py`. W repozytorium jest
  tylko opis sceny i mapa ról.
- **Obrys pokoju to prostokąt.** Ściana kolankowa i skos są w geometrii, ale
  nie w `polygon_xy_m`, więc lampa i punkt startowy liczą się z prostokąta,
  a wycena powierzchni ścian z tego pliku wyszłaby za duża.
- Scena źródłowa ma status `draft`: wymiary są odczytem ze zdjęć, nie
  pomiarem, a wariant `premium` jest propozycją bez cen i bez zgód.

## Kadry na stronę

```powershell
powershell -ExecutionPolicy Bypass -File unreal\tools\render_shots.ps1
powershell -ExecutionPolicy Bypass -File unreal\tools\render_shots.ps1 -Res 3840x2160
```

Jeden PNG na wariant i widok, do `work/renders`. Kadry biorą się z
`presentation.views` w `scene.json`, więc dopisany widok od razu ma swoje
zdjęcie. Kamera stoi na wysokości oczu (1,55 m) i **trzyma poziom** — pion
zostaje pionem, tak jak w fotografii architektury.

Trzy rzeczy, które trzeba było obejść, bo każda kosztowała podejście:

- **`-ExecCmds=py <ścieżka>` rozpada się na spacji** i silnik wykonuje samo
  `py`. Komenda idzie więc przez plik `.cmd`, gdzie cudzysłowy są nasze.
- **`-ExecutePythonScript=` zamyka edytor natychmiast po skrypcie**, a nasz
  tylko rejestruje pętlę po ticku i wraca — edytor gasł przed pierwszą
  klatką.
- **W jednej sesji wychodzi tylko pierwszy kadr.** Kolejne `HighResShot`
  zostają w kolejce i nigdy się nie wykonują; wymuszanie odrysowania
  (`editor_invalidate_viewports`) ani wyłączanie usypiania w tle nie pomogło.
  Dlatego jeden kadr na uruchomienie edytora (`ROOM_SHOT_INDEX`): około
  45 sekund na zdjęcie, ale wychodzi za każdym razem.

Przed zdjęciem skrypt wychodzi z pilotowania aktora, odznacza zaznaczenie
i włącza tryb gry — inaczej w kadrze siedzi pomarańczowy obrys zaznaczenia,
wskaźnik osi i siatka, a kamera wraca na pozycję pilotowanego aktora.
Czeka też 90 klatek, żeby Lumen zdążył policzyć światło odbite; bez tego
w cieniach zostaje szum.

## Poziom jest wynikiem, nie źródłem

Każda budowa **kasuje i stawia poziom od nowa** — razem z materiałami
i siatkami. Cokolwiek wyklikasz w edytorze (przesunięta lampa, inna
intensywność nieba, podmieniony materiał), zniknie przy następnym
uruchomieniu skryptu. Zmiany, które mają zostać, idą do:

- `datasets/pokoj-poddasze/scene.json` — wykończenia, tekstury, warianty,
  otwory (a z nich światła okien), obrys, widoki startowe;
- `datasets/pokoj-poddasze/role-map.json` — co jest ścianą, a co meblem;
- `unreal/tools/import_scene.py` — światła, materiał bazowy, ekspozycja;
- sam `.blend` — geometria.

Edytor jest do oglądania i do sprawdzania wartości. Jak coś w nim wyjdzie
lepiej niż w skrypcie, trzeba tę liczbę przepisać do skryptu.

## Co jest w repozytorium

Tylko źródła: `RoomDemo.uproject`, `Config/` i skrypty. Katalogi `Content`,
`Saved`, `Intermediate` i `DerivedDataCache` powstają z FBX i `scene.json`,
więc `.gitignore` je pomija. Poziom odtwarza się jedną komendą.
