# Room

Platforma B2B do interaktywnych wizualizacji wnętrz nieruchomości w przeglądarce.

## Cel i status
Zamienić rzut i zdjęcia lokalu w scenę o sprawdzonych wymiarach, umeblowaną rzeczywistymi produktami, a następnie udostępnić spacer i warianty aranżacji przez stronę internetową.
Stan: działa warstwa danych i generator geometrii. Scene.json ma walidator, a zatwierdzona scena buduje się w Blenderze i eksportuje do FBX/glTF. Nie ma jeszcze modelu AI, katalogu produktów, aplikacji Unreal ani uruchomionego streamingu.

## Cele krok po kroku
1. Pozyskać rzut z wymiarami, wysokość pomieszczeń i zdjęcia jednego lokalu.
2. Wyodrębnić strukturę do JSON; oznaczyć źródła, niepewność i brakujące pomiary.
3. Zatwierdzić geometrię z człowiekiem przed budowaniem sceny.
4. Zbudować ściany, podłogę i otwory w Blenderze; ustawić licencjonowane modele produktów.
5. Przygotować dwa zestawy materiałów i mebli dla tego samego lokalu.
6. Zaimportować scenę do Unreal, dodać kolizje, kamerę, światło i zmianę wariantu.
7. Spakować aplikację i uruchomić Pixel Streaming na GPU.
8. Osadzić spacer na stronie z ofertą i formularzem kontaktowym.
9. Zmierzyć jakość, koszt sesji i zainteresowanie płatnym pilotem.
10. Dopiero po pilocie rozszerzyć produkt o polecenia AI, katalog i wdrożenia wielu klientów.

## Zakres MVP
- Jeden typ mieszkania, dwóch wariantów wystroju nie generujemy od nowa przy każdym kliknięciu.
- Dane wejściowe: PDF/PNG/JPG rzutu, zdjęcia, co najmniej jeden wiarygodny wymiar referencyjny i wysokość.
- Półautomatyczna analiza AI z obowiązkową korektą operatora.
- Mały katalog: 5–10 licencjonowanych modeli, identyfikator produktu, wymiary, źródło i materiał.
- Spacer w przeglądarce na komputerze; dotyk i telefon sprawdzane w pilocie.
- Start/koniec sesji, ekran ładowania, komunikat błędu, reset widoku, wybór stylu.
- Jedna równoczesna sesja pilota; dodatkowe sesje dopiero po pomiarze zasobów.
- Podstawowy branding i kontakt do sprzedawcy.

Poza MVP: płatności, koszyk, wieloklientowy panel, automatyczny cold outreach, pełna fotogrametria, dowolne przebudowy głosowe i automatyczna rekonstrukcja dowolnego lokalu bez kontroli.

## Architektura i przepływ
Rzut + zdjęcia → backend/analiza AI → kandydat scene.json → walidacja operatora
→ Blender/Python + katalog modeli → plik .blend + eksport geometrii
→ Unreal (import, światło, kolizje, warianty) → spakowana aplikacja na GPU
→ Pixel Streaming/WebRTC → przeglądarka.

Strona przesyła sterowanie i identyfikator wariantu do działającej aplikacji. Backend obsługuje zadania przygotowania sceny i stan sesji. Model AI nie tworzy bezpośrednio binarnych .uasset i nie wykonuje dowolnego kodu w aplikacji klienta.
Blender automatyzuje przygotowanie geometrii; Unreal renderuje scenę. Odtwarzanie filmu AI nie zastępuje spójnej, interaktywnej geometrii.

## Struktura
- blender/scripts/ — walidator, generator geometrii i eksporter; rdzen `roomlib` liczy wymiary bez Blendera i ma testy jednostkowe.
- unreal/ — miejsce na rzeczywisty projekt utworzony w edytorze.
- web/ — frontend oferty, streamingu i wyboru wariantów.
- backend/ — analiza wejścia, zadania, walidacja i sesje.
- catalog/ — indeks produktów i metadane praw do modeli.
- datasets/sample/ — syntetyczny przykład kontraktu, miejsce na wejście i zatwierdzone dane.
- docs/ — architektura, wymagania i harmonogram.
- deploy/ — instrukcje uruchomienia lokalnego oraz hostingu GPU.
- work/ — lokalne wyniki robocze, poza repozytorium.

## Kamienie milowe i odbiór
| Etap | Rezultat | Warunek odbioru |
|---|---|---|
| M0: wejście | Materiały jednego lokalu | Prawa do materiałów, jednostki i brakujące wymiary opisane |
| M1: geometria | Zatwierdzony JSON i model Blender | Wymiary porównane z rzutem, otwory i skala potwierdzone |
| M2: wnętrze | Dwa warianty tej samej sceny | Brak przenikania mebli, zgodność rozmiarów produktów |
| M3: Unreal | Lokalny build | Spacer, kolizje i przełączanie wariantów działają |
| M4: web | Sesja przez internet | Test w dwóch sieciach, odzyskiwanie po rozłączeniu, limit bezczynności |
| M5: pilot | Demo i oferta | Zmierzony koszt 10 minut, rozmowy z klientami i decyzja o płatnym pilocie |

Kolejność jest planem, nie obietnicą terminu. Estymacja po sprawdzeniu materiałów i pierwszej scenie.

## Założenia i ryzyka
- Zdjęcia służą jako referencja; niewidoczna geometria nie może być traktowana jako ustalony fakt.
- Jeden wymiar skaluje rzut, ale nie gwarantuje poprawności pozostałych pomiarów.
- Import do Unreal wymaga kontroli materiałów, osi, skali i kolizji; nie zakładamy bezstratnego transferu.
- Niezależni użytkownicy potrzebują odrębnego stanu i renderowania; liczba sesji na GPU zależy od benchmarku.
- Wybrać i przypiąć wersje Blender, Unreal, wtyczki oraz infrastruktury Pixel Streaming po próbie zgodności.
- Hosting zarządzany jest wariantem startowym; dostawca, koszty i limity pozostają do wyceny.
- Ceny pilota 7 900–9 900 zł netto z rozmowy są hipotezą sprzedażową, a nie potwierdzoną ceną rynkową.
- Koszt obejmuje opracowanie sceny, modele/licencje, GPU, transfer, magazyn danych, AI i wsparcie.
- Potrzebna osoba zatwierdzająca geometrię oraz operator Blender/Unreal do jakości wizualnej.
- Nie publikować danych klientów ani kluczy API. Ustalić retencję i możliwość usunięcia wejścia.

## Najbliższa czynność
Dodać jeden rzut z wymiarami i zdjęcia do lokalnego datasets/sample/input/, przepisać go ręcznie na scene.json i doprowadzić do statusu approved. Przykładowy JSON obok jest fikcyjny i ma status example_only, więc generator odmówi zbudowania go bez jawnego --allow-unapproved.

Sprawdzenie i zbudowanie sceny:

    python3 blender/scripts/validate_scene.py --scene <plik>
    blender --background --python-exit-code 1 --python blender/scripts/build_scene.py -- --scene <plik>
    blender --background work/scenes/<scene_id>/<scene_id>.blend --python blender/scripts/export_scene.py -- --format fbx

Testy rdzenia (bez Blendera):

    python3 -m unittest discover -s blender/scripts/tests -t blender/scripts

Szczegóły i ograniczenia: blender/scripts/README.md.

## Dokumenty
- docs/architecture.md — kontrakty i odpowiedzialności
- docs/roadmap.md — backlog i walidacja sprzedaży
- deploy/README.md — uruchomienie i pomiary

## Dokumentacja techniczna
- Epic: https://dev.epicgames.com/documentation/en-us/unreal-engine/pixel-streaming-in-unreal-engine
- Epic start: https://dev.epicgames.com/documentation/en-us/unreal-engine/getting-started-with-pixel-streaming-in-unreal-engine
- Blender Python: https://developer.blender.org/docs/handbook/testing/python/
Źródła sprawdzone 2026-09-06; ceny usług nie były aktualizowane.