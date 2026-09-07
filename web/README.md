# Room — główne demo standalone

Aktualizacja: 7 września 2026. Główna scena to umeblowany parter z `datasets/sample/kruszczyki-22/scene.json`. Pokój użytkownika jest osobnym testem rekonstrukcji.

## Uruchomienie

Otwórz `web/standalone.html` dwuklikiem w Edge lub Chrome. Model, dane i biblioteki są osadzone w jednym pliku (~4,5 MiB), bez połączeń HTTP. Wersję rozdzieloną można uruchomić lokalnie:

    python -m http.server --directory web 8080

## Aktualizacja całej sceny

    python web/tools/build_showcase.py

Jeżeli Blender jest w innej lokalizacji:

    python web/tools/build_showcase.py --blender "ścieżka/do/blender.exe"

Komenda buduje scenę Blender, eksportuje GLB z identyfikatorami mebli, składa standalone i aktualizuje `web/scene.json`, `web/assets/room.glb`, `web/standalone.html` oraz `web/build-manifest.json`. Wyniki i logi robocze trafiają do `work/scenes/showcase/`. Dane i katalog nie mogą zmienić się w trakcie budowania. Scena zachowuje status draft; jest to przygotowanie lokalnego podglądu.

Przy zmianach samego interfejsu:

    python web/tools/build_standalone.py

Ta druga komenda nie aktualizuje geometrii ani manifestu pełnej budowy.

## Prezentacja

- Start w Premium, widok makiety z obniżonymi ścianami. Przycisk „Niskie ściany” pozwala pokazać pełną wysokość. Geometria źródłowa nie jest przycinana — to zabieg widoku w przeglądarce.
- Basic/Premium podmieniają materiały powierzchni, bez zmiany układu wyposażenia.
- Lista pomieszczeń otwiera spacer z dobranego punktu. Preferowane kadry zapisuje pole `presentation.views` w źródłowym JSON.
- Światło dzienne i wieczorne, lokalne światła we wnętrzach, neutralna paleta tkanin poglądowych i drewna.
- „Od nowa” wraca do widoku całej sceny. „Spacer” otwiera ostatnio wybrane pomieszczenie.
- Informacje o źródłach i przybliżeniach są dostępne w rozwijanym „O scenie”.

## Sterowanie

Makieta: przeciąganie obraca, kółko myszy przybliża. Spacer: przeciąganie rozgląda, WASD lub strzałki poruszają, Shift przyspiesza, Esc wraca do makiety. Na urządzeniach dotykowych spacer ma dodatkowe przyciski kierunkowe. Kadrowanie makiety dopasowuje się do wąskiego ekranu.

Ruch uwzględnia obrysy pomieszczeń i gabaryty mebli stojących na podłodze. Przejścia są tworzone tylko, gdy otwór łączy sąsiadujące pomieszczenia. Kolizje mebli są przybliżeniem opartym na osiowych gabarytach, nie pełną fizyką siatki. Nie zastępują kontroli zgodności rzutu; nie rozwiązują brakujących fragmentów korytarza w danych źródłowych.

## API

`window.RoomViewer` udostępnia: `setMode('walk'|'orbit')`, `reset()`, `visitRoom(id)`, `canStand(x,y)`, `setVariant(id)`, `listVariants()`, `listFinishes()`, `on(event, callback)` oraz stan `mode`, `activeVariant`, `lighting`, `cutaway`, `sceneData`.

Układ współrzędnych: punkt rzutu `(x,y)` odpowiada światu three.js `(x, wysokość, -y)`.

## Sprawdzenie

Sprawdzono lokalny HTTP i samodzielny HTML, oba wykończenia, zmianę oświetlenia, przycinanie ścian, nawigację po pomieszczeniach, ruch i reset. Widoki skontrolowano na pulpicie i w emulacji 390 px. Rzeczywisty telefon i Safari wymagają osobnego odbioru. Dowody bieżącej sesji są w `work/audit/`.

Geometria nadal jest wersją roboczą. Ta iteracja poprawia główną scenę i prezentację; nie dodaje ekstrakcji AI ani Pixel Streamingu.
