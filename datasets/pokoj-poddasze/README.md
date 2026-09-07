# Pokój na poddaszu — kontrakt sceny

`scene.json` opisuje pokój tak samo, jak `kruszczyki-22/scene.json` opisuje
mieszkanie: obrys, wysokość, otwory, wykończenia i warianty. Różnica jest
jedna i trzeba o niej pamiętać:

**Geometria nie powstaje z tego pliku.** Pochodzi z rekonstrukcji ze zdjęć —
`work/scenes/attic-room-v06/Room-attic-v06.blend`. Katalog `work/` jest poza
repozytorium, więc na nowej maszynie trzeba ten blend mieć albo odtworzyć
skryptami `blender/scripts/reconstruct_attic*.py` i `refine_*_v0*.py`.
`scene.json` daje reszcie potoku to, czego blend nie niesie: obrys do świateł
i punktu startowego, wykończenia i dwa warianty.

`role-map.json` uzupełnia drugą brakującą rzecz — role. Blend nie ma
właściwości `role` ani `room_id`, bo nie powstał z `build_scene.py`, więc role
nadajemy po nazwach obiektów. Wygrywa najdłuższy pasujący prefiks: dzięki temu
`High wall skirting` idzie do listwy, a nie do ściany. Co nie pasuje do żadnej
reguły, zostaje meblem i zachowuje własny materiał z blenda — grzejnik,
gniazda, łóżko i lampy nie zmieniają się z wariantem.

## Budowa poziomu w Unrealu

```powershell
powershell -ExecutionPolicy Bypass -File unreal\tools\build_unreal.ps1
```

To są domyślne wartości skryptu. Mieszkanie demo buduje się tą samą komendą
z innymi parametrami:

```powershell
powershell -ExecutionPolicy Bypass -File unreal\tools\build_unreal.ps1 `
    -Blend work\scenes\showcase\main.blend `
    -Scene datasets\sample\kruszczyki-22\scene.json -Roles ""
```

## Czego ten opis nie mówi

Obrys jest prostokątem 2,90 × 4,12 m. Ściana kolankowa (1,07 m) i skos do
sufitu płaskiego (2,32 m) są w geometrii, ale nie w obrysie — wycena
powierzchni ścian z tego pliku wyszłaby za duża. Okno połaciowe siedzi
w skosie, więc nie ma go na liście otworów.

Wariant `basic` odtwarza kolory z rekonstrukcji, `premium` jest propozycją.
Żadna pozycja nie ma ceny ani zgody producenta, dlatego scena ma status
`draft`.
