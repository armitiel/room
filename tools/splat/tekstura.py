"""Ortofoto narzuty z gory - gotowe do uzycia jako tekstura w modelu.

Splat nie da czystej siatki, ale da cos, czego model dzis nie ma wcale:
prawdziwy rysunek narzuty w rzucie prostopadlym, w metrach. Bierzemy pas
punktow wokol gornej powierzchni, rzutujemy go na plaszczyzne lozka
i rasteryzujemy w stalej rozdzielczosci pikseli na metr.

Dziury po brakujacych punktach zalepiamy rozmyciem promieniowym: piksel bez
trafienia dostaje srednia z sasiadow, powtorzone kilka razy. To nie jest
rekonstrukcja - to laty, i tak sa oznaczone w raporcie liczba trafien.
"""

import json
import sys

import numpy as np
from PIL import Image

# Gestosc punktow na narzucie to okolo 40 tys. na metr kwadratowy, czyli
# jeden punkt co jakies 5 mm. Przy 700 px/m wypelnialo sie 7% pikseli i
# obraz byl bardziej latany niz mierzony. 250 px/m odpowiada danym.
PIKSELI_NA_METR = 250


def main():
    dane = np.load(sys.argv[1])
    katalog = sys.argv[2]
    lokalne = dane["lokalne"].astype(np.float64)
    kolor = dane["kolor"].astype(np.float64)

    wys = lokalne[:, 2]
    licznik, kraw = np.histogram(wys, bins=400)
    srodki = (kraw[:-1] + kraw[1:]) / 2
    szczyt = float(srodki[np.argmax(licznik)])

    # Pas wysokosci nie sprawdzil sie: narzuta nie jest plaska, wiec staly
    # przedzial wycinal dziury tam, gdzie tkanina opada. Zamiast tego
    # bierzemy wszystko od 12 cm ponizej szczytu w gore i dla kazdego piksela
    # zostawiamy punkt najwyzszy - to jest dokladnie widok z gory.
    pas = wys > szczyt - 0.12
    punkty = lokalne[pas]
    barwy = kolor[pas]

    # Obrys prostokata z 1. i 99. percentyla - odcina pojedyncze odpryski.
    dol = np.percentile(punkty[:, :2], 1.0, axis=0)
    gora = np.percentile(punkty[:, :2], 99.0, axis=0)
    boki = gora - dol
    szer = int(round(boki[0] * PIKSELI_NA_METR))
    wysk = int(round(boki[1] * PIKSELI_NA_METR))

    px = ((punkty[:, 0] - dol[0]) / boki[0] * (szer - 1)).astype(np.int32)
    py = ((punkty[:, 1] - dol[1]) / boki[1] * (wysk - 1)).astype(np.int32)
    ok = (px >= 0) & (px < szer) & (py >= 0) & (py < wysk)
    px, py, barwy = px[ok], py[ok], barwy[ok]
    wysokosci = punkty[ok, 2]
    py = wysk - 1 - py

    # Bufor glebokosci od gory: malujemy od najnizszych do najwyzszych,
    # wiec w pikselu zostaje punkt lezacy najwyzej.
    kolejnosc = np.argsort(wysokosci)
    obraz = np.zeros((wysk, szer, 3), dtype=np.float64)
    trafione = np.zeros((wysk, szer), dtype=bool)
    obraz[py[kolejnosc], px[kolejnosc]] = barwy[kolejnosc]
    trafione[py[kolejnosc], px[kolejnosc]] = True

    pokrycie_przed = float(trafione.mean())
    # Latanie dziur: srednia z czterech sasiadow, tylko tam gdzie pusto.
    maska = trafione.copy()
    for _ in range(30):
        if maska.all():
            break
        sasiedzi = np.zeros_like(obraz)
        licz = np.zeros((wysk, szer), dtype=np.float64)
        for przesuniecie in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            przes = np.roll(obraz, przesuniecie, axis=(0, 1))
            maska_p = np.roll(maska, przesuniecie, axis=(0, 1))
            sasiedzi += przes * maska_p[:, :, None]
            licz += maska_p
        puste = (~maska) & (licz > 0)
        obraz[puste] = sasiedzi[puste] / licz[puste, None]
        maska = maska | puste

    Image.fromarray((np.clip(obraz, 0, 1) * 255).astype(np.uint8)).save(
        katalog + "/narzuta_ortofoto.png")

    srednia = barwy.mean(axis=0)
    ciemne = barwy[barwy.sum(axis=1) < np.percentile(barwy.sum(axis=1), 60)]
    jasne = barwy[barwy.sum(axis=1) > np.percentile(barwy.sum(axis=1), 95)]
    raport = {
        "plik": "narzuta_ortofoto.png",
        "piksele": [szer, wysk],
        "wymiar_m": [round(float(boki[0]), 3), round(float(boki[1]), 3)],
        "pikseli_na_metr": PIKSELI_NA_METR,
        "punktow_uzytych": int(len(px)),
        "pokrycie_przed_lataniem": round(pokrycie_przed, 3),
        "kolor_sredni_hex": "#%02x%02x%02x" % tuple((srednia * 255).astype(int)),
        "kolor_tla_hex": "#%02x%02x%02x" % tuple((ciemne.mean(axis=0) * 255).astype(int)),
        "kolor_wzoru_hex": "#%02x%02x%02x" % tuple((jasne.mean(axis=0) * 255).astype(int)),
    }
    print(json.dumps(raport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
