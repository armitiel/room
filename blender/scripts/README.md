# Blender/Python

## Co tu jest

    roomlib/            wspólny rdzeń bez zależności od Blendera
      constants.py      stałe kontraktu: wersje schematu, statusy, tolerancje
      geometry.py       geometria 2D rzutu: pole, ściany, samoprzecięcia, kolizje mebli
      scene_io.py       odczyt i zapis scene.json oraz katalogu produktów
      validate.py       reguły walidacji sceny
      build_plan.py     zamiana sceny na plan brył: ściany, naroża, otwory
    validate_scene.py   walidator z linii poleceń (czysty Python)
    build_scene.py      generator geometrii (wymaga Blendera)
    export_scene.py     eksport do FBX/glTF (wymaga Blendera)
    tests/              testy jednostkowe, uruchamiane bez Blendera

Podział jest celowy: cała arytmetyka siedzi w `roomlib` i jest pokryta testami,
które uruchamiają się w kilka milisekund. Skrypty Blendera nie liczą nic własnego —
wykonują gotowy plan. Dzięki temu błąd wymiarowy widać w teście, a nie dopiero
na renderze.

Kod w plikach .py jest pisany bez polskich znaków diakrytycznych, żeby konsola
Blendera na Windows nie miała problemu z kodowaniem. Dokumentacja ich używa.

## Uruchomienie

Walidacja (nie wymaga Blendera):

    python3 blender/scripts/validate_scene.py --scene datasets/sample/approved/scene.json
    python3 blender/scripts/validate_scene.py --scene <plik> --json --out work/report.json
    python3 blender/scripts/validate_scene.py --scene <plik> --require-buildable

Kody wyjścia: 0 brak błędów, 1 błędy lub scena nie do budowy, 2 błąd odczytu pliku.

Sam plan, bez budowania geometrii:

    python3 blender/scripts/build_scene.py --scene <plik> --plan-only --allow-unapproved

Budowa sceny:

    blender --background --python-exit-code 1 \
        --python blender/scripts/build_scene.py -- --scene <plik> --placeholders

Eksport gotowego pliku:

    blender --background work/scenes/<scene_id>/<scene_id>.blend \
        --python blender/scripts/export_scene.py -- --format fbx

Testy:

    python3 -m unittest discover -s blender/scripts/tests -t blender/scripts

## Zasady, które te skrypty egzekwują

Generator nie buduje sceny, która ma błędy walidacji. Scena bez statusu
`approved` wymaga jawnego `--allow-unapproved`, a wynik jest podglądem
roboczym, nie dostawą.

Wielokąt w `scene.json` opisuje WEWNĘTRZNE lico ścian. Ściany rosną na zewnątrz,
więc wymiary w świetle zgadzają się z rzutem. Naroża liczą się jako przecięcie
odsuniętych prostych, więc ściany stykają się bez szczelin także w narożach
wklęsłych.

`offset_m` otworu liczy się od początku ściany tak, jak zapisano ją w pliku.
Jeśli rzut podano w kolejności zgodnej z ruchem wskazówek zegara, generator
normalizuje kolejność wierzchołków, ale odbija tę odległość, żeby otwór
wylądował tam, gdzie na rzucie.

Bryły tnące otwory (`cut_*`) i bryły zastępcze (`PLACEHOLDER_*`) nigdy nie
trafiają do eksportu. Brak modelu produktu jest zgłaszany, a nie zastępowany
po cichu czymkolwiek.

Każdy obiekt niesie właściwości `room_id`, `wall_index`, `furniture_id`
i `product_id`, żeby identyfikatory przetrwały drogę do Unreal.

## Jednostki i osie

Blender pracuje w metrach, Unreal w centymetrach. `export_scene.py --units cm`
stosuje mnożnik 100 przy eksporcie FBX i zapisuje użyte ustawienia obok pliku
w `<nazwa>_export_report.json`. glTF z definicji zapisuje metry, więc dla tego
formatu skala pozostaje 1.0 i raport tak właśnie podaje.

Konwencja osi FBX (`-Z` w przód, `Y` w górę) jest wartością startową do
sprawdzenia przy PIERWSZYM imporcie w Unreal, nie pewnikiem. Raport eksportu
zawiera listę rzeczy do zmierzenia po imporcie.

## Czego tu jeszcze nie ma

Materiałów i wariantów wykończenia. Światła i kamer. Obsługi wielu pomieszczeń
połączonych przejściami — każde pomieszczenie budowane jest osobno, więc wspólna
ściana między dwoma pokojami powstanie dwa razy.
