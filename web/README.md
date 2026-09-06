# Frontend

Przeglądarka sceny działająca w całości po stronie klienta: scena glTF renderowana
przez three.js na karcie graficznej osoby, która otworzy link. Bez serwera GPU,
bez streamingu, bez konta u dostawcy — hosting statyczny wystarczy.

## Pliki

    index.html                 strona i przeglądarka (jeden plik, bez kroku budowania)
    scene.json                 metadane sceny: obrys, wysokość, otwory, status
    assets/room.glb            geometria wyeksportowana z Blendera
    vendor/three/              three.js r169, licencja MIT, dołączona obok
    standalone.html            wszystko w jednym pliku, działa offline z dysku
    tools/build_standalone.py  składa standalone.html z powyższych

Biblioteka leży w repozytorium, a nie na CDN-ie, celowo. Demo sprzedażowe nie
może paść dlatego, że w sali konferencyjnej klienta jest słaby internet albo
firewall blokuje zewnętrzne domeny. Cena: ~850 kB w repo.

## Uruchomienie

Z dysku, bez niczego — także bez internetu:

    otwórz web/standalone.html dwuklikiem

`standalone.html` (~1,2 MB) ma w środku model, scenę i całą bibliotekę.
Sprawdzone: otwiera się z `file://` i renderuje bez połączenia z siecią.

Przez serwer (potrzebne dla `index.html`, bo przeglądarki blokują `fetch`
dla adresów `file://`):

    python3 -m http.server --directory web 8080

Publicznie: włącz GitHub Pages dla katalogu `web/` i dostajesz link,
który możesz wysłać deweloperowi.

## Skąd biorą się pliki

    blender --background --python-exit-code 1 --python blender/scripts/build_scene.py -- \
        --scene datasets/sample/demo/scene.json --allow-unapproved --ceiling
    blender --background work/scenes/demo-room-001/demo-room-001.blend \
        --python blender/scripts/export_scene.py -- --format glb --units m

Potem skopiuj `.glb` do `web/assets/room.glb`, `scene.json` do `web/scene.json`
i przebuduj wersję osadzoną:

    python3 web/tools/build_standalone.py

## API dla strony

`window.RoomViewer` to jedyna powierzchnia, przez którą strona rozmawia
z przeglądarką sceny:

    RoomViewer.setMode('walk' | 'orbit')
    RoomViewer.reset()
    RoomViewer.canStand(px, py)          // czy w tym punkcie rzutu da się stanąć
    RoomViewer.worldFromPlan(px, py)     // rzut → scena
    RoomViewer.planFromWorld(x, z)       // scena → rzut
    RoomViewer.listVariants()
    RoomViewer.setVariant(id)
    RoomViewer.on('ready' | 'variantchange', handler)

To samo API ma obsłużyć obie ścieżki renderowania. Dziś `setVariant` podmienia
materiały lokalnie; przy Pixel Streamingu będzie wysyłać identyfikator do
działającej aplikacji Unreal. Strona nie musi wiedzieć, co jest pod spodem.

## Sterowanie

Tryb **Rzut**: przeciągnij, żeby obrócić, przewiń, żeby przybliżyć. Działa
także dotykiem, więc na telefonie to jest ten tryb.

Tryb **Spacer**: przeciągnij albo kliknij, żeby się rozglądać, `W` `A` `S` `D`
chodzą, `Shift` przyspiesza, `Esc` wychodzi. Rozglądanie działa również dotykiem
i wewnątrz ramki `iframe`, bo nie polegamy na blokadzie kursora — jest tylko
ułatwieniem, nie warunkiem. Chodzenie wymaga klawiatury, więc na telefonie
właściwym trybem pozostaje „Rzut”.

## Kolizje

Ściany zatrzymują na podstawie **wielokąta z `scene.json`**, a nie siatki 3D.
Dzięki temu wynik zgadza się z wymiarami z umowy, a wycięty otwór drzwiowy
nadal jest ścianą, przez którą nie da się przejść. Promień „ciała" to 0,35 m,
wysokość oczu 1,65 m. Przy zablokowanym ruchu na wprost próbowany jest ruch
wzdłuż każdej z osi osobno, więc idzie się po ścianie, a nie zatrzymuje w miejscu.

## Układ współrzędnych

Blender eksportuje glTF w konwencji Y w górę. Punkt rzutu `(px, py)` z `scene.json`
odpowiada pozycji świata `(x = px, z = -py)`. Ta zamiana jest w jednym miejscu
w `index.html` — jeśli kiedykolwiek zmienimy ustawienia eksportu, trzeba poprawić
tam i w `export_scene.py`, nigdzie indziej.

## Co zostało sprawdzone

Renderowanie i sterowanie przetestowane w Chromium: obrys L z czterema otworami
wczytuje się, panel pokazuje 24,0 m², kolizje trzymają. Punkty sprawdzone:
środek obu części L — można stanąć; wcięcie L i teren poza obrysem — nie;
0,1 m od ściany — nie; 0,5 m — tak; **w świetle wyciętych drzwi — nie**, czyli
otwór w siatce nie jest dziurą w kolizji. Marsz na wprost zatrzymuje się
0,35 m przed ścianą i ślizga wzdłuż niej zamiast blokować w miejscu.

## Czego tu jeszcze nie ma

Wariantów wykończenia (API jest przygotowane, ale generator nie tworzy jeszcze
wariantów). Formularza kontaktowego i sekcji ofertowej. Ekranu kolejki i obsługi
sesji — te są potrzebne dopiero przy Pixel Streamingu.
