# Pomiary ze skanu gaussowskiego (3DGS)

Zestaw skryptów, którymi zmierzono łóżko z pliku `work/Osowa.ply`
(397 047 gaussianów, harmoniczne stopnia 3). Wyniki trafiły do
`blender/scripts/refine_bed_v06.py`.

Splat nie daje siatki — daje chmurę punktów z kolorem. Nadaje się do
**wymiarów i barw**, nie do geometrii. Te skrypty pilnują tej granicy:
każdy liczy jedną rzecz i wypisuje JSON, żeby dało się sprawdzić, skąd
wzięła się liczba.

## Kolejność

```
python tools/splat/naglowek.py work/Osowa.ply
python tools/splat/wczytaj.py  work/Osowa.ply work/scan/scena.npz
python tools/splat/pomiar.py   work/scan/scena.npz 2.0
python tools/splat/widoki.py   work/scan/scena_lokalne.npz work/scan
```

`wczytaj.py` pomija 45 kolumn `f_rest_*` — to 72% pliku i nie mówi nic
o wymiarach. `pomiar.py` znajduje układ własny obiektu (PCA), prostuje go
i zapisuje `*_lokalne.npz`; wszystkie dalsze skrypty pracują już w tym
układzie, z zerem na wierzchu mierzonej powierzchni.

## Do czego służy który

| skrypt | odpowiada na pytanie |
|---|---|
| `naglowek.py` | co jest w pliku: ile punktów, jakie pola, czy to w ogóle 3DGS |
| `wczytaj.py` | gdzie jest scena, a gdzie tło rozciągnięte „w nieskończoność" |
| `pomiar.py` | orientacja, prostokąt opisujący, profil wysokości |
| `widoki.py` | rzuty w układzie obiektu + prostokąt warstwami wysokości |
| `proporcje.py` | proporcje liczone kilkoma definicjami krawędzi naraz |
| `obrys_narzuty.py` | rozdzielenie tkaniny od tła po barwie |
| `rant.py` | mediana wysokości pasmami od brzegu |
| `oparcie.py` | grubość i wysokość pionowego elementu przy krawędzi |
| `sylwetka.py` | przekrój z jasnością od gęstości punktów |
| `mapa_wysokosci.py` | rzut z góry, kolor = wysokość |
| `tekstura.py` | ortofoto powierzchni, bufor głębokości od góry |
| `kadr.py` | wycięcie tekstury do dokładnego prostokąta w metrach |

## Dwie pułapki, na które się nadziałem

**Percentyl to nie krawędź.** Obrys liczony percentylem 0,5/99,5 dał
1,99 × 1,58 m i wyglądał sensownie. Krawędź liczona spadkiem gęstości
pokazała, że rdzeń ma 1,63 × 1,58 m — czyli na łóżku leży osobna,
kwadratowa tkanina. Dwie definicje, dwa różne wnioski; `proporcje.py`
liczy obie naraz właśnie dlatego.

**Mapa wysokości pokazuje maksimum, nie powierzchnię.** Jasna obwódka
wokół posłania wyglądała jak podniesiony rant i prawie trafiła do modelu.
`rant.py` policzył medianę pasmami od brzegu — płasko, rozrzut ±8 cm.
Rantu nie ma.

## Czego z tego nie da się wyciągnąć

Wysokości nad podłogą, jeśli skan nie objął boków mebla. Geometrii
(krawędzie są rozmyte z definicji). Niczego w miejscach, gdzie punktów
jest kilkaset — przy krawędzi mebla mieszają się z tym, co stoi obok.
