"""Widoki w ukladzie samego obiektu, plus prostokat mierzony warstwami.

Rzut z gory jest tu wyprostowany: obiekt lezal skosnie wzgledem osi pliku,
wiec dopiero po obrocie do jego wlasnego ukladu widac rzeczywisty ksztalt.

Prostokat liczony osobno dla kolejnych warstw wysokosci odpowiada na
pytanie, czy 2,44 x 2,02 m to blat, czy zwisajaca narzuta - jesli obrys
rosnie w dol, to tkanina; jesli jest staly, to bryla.
"""

import json
import sys

import numpy as np
from PIL import Image


def rysuj(punkty, barwy, os_a, os_b, sciezka, rozmiar=1400, tlo=14):
    a, b = punkty[:, os_a], punkty[:, os_b]
    glebia = punkty[:, 3 - os_a - os_b]
    zakres = max(a.max() - a.min(), b.max() - b.min()) * 1.05
    sa, sb = (a.min() + a.max()) / 2, (b.min() + b.max()) / 2
    skala = rozmiar / zakres
    px = ((a - sa) * skala + rozmiar / 2).astype(np.int32)
    py = rozmiar - 1 - ((b - sb) * skala + rozmiar / 2).astype(np.int32)
    ok = (px >= 0) & (px < rozmiar) & (py >= 0) & (py < rozmiar)
    px, py, kol, gl = px[ok], py[ok], barwy[ok], glebia[ok]
    kolejnosc = np.argsort(-gl)
    obraz = np.full((rozmiar, rozmiar, 3), tlo, dtype=np.uint8)
    obraz[py[kolejnosc], px[kolejnosc]] = (kol[kolejnosc] * 255).astype(np.uint8)
    Image.fromarray(obraz).save(sciezka)
    return round(float(skala), 1)


def prostokat(punkty_2d):
    najlepsze = None
    for kat in np.arange(0.0, 90.0, 0.5):
        r = np.radians(kat)
        c, s = np.cos(r), np.sin(r)
        obr = punkty_2d @ np.array([[c, -s], [s, c]])
        boki = np.percentile(obr, 99.5, axis=0) - np.percentile(obr, 0.5, axis=0)
        pole = boki[0] * boki[1]
        if najlepsze is None or pole < najlepsze[0]:
            najlepsze = (pole, sorted(boki, reverse=True))
    return najlepsze


def main():
    dane = np.load(sys.argv[1])
    katalog = sys.argv[2]
    lokalne = dane["lokalne"].astype(np.float64)
    kolor = dane["kolor"]
    wys = lokalne[:, 2]
    dol = np.percentile(wys, 0.5)
    gora = np.percentile(wys, 99.5)

    raport = {"px_na_m": {}}
    raport["px_na_m"]["gora"] = rysuj(lokalne, kolor, 0, 1, katalog + "/obiekt_gora.png")
    raport["px_na_m"]["bok_dlugi"] = rysuj(lokalne, kolor, 0, 2, katalog + "/obiekt_bok.png")
    raport["px_na_m"]["bok_krotki"] = rysuj(lokalne, kolor, 1, 2, katalog + "/obiekt_czolo.png")

    warstwy = []
    for i in range(10):
        a = dol + (gora - dol) * i / 10.0
        b = dol + (gora - dol) * (i + 1) / 10.0
        maska = (wys >= a) & (wys < b)
        if np.count_nonzero(maska) < 500:
            warstwy.append({"od_dolu_m": round(a - dol, 3), "punktow": int(maska.sum()),
                            "prostokat": None})
            continue
        pole, boki = prostokat(lokalne[maska][:, :2])
        warstwy.append({
            "od_dolu_m": round(a - dol, 3),
            "punktow": int(maska.sum()),
            "dluzszy_m": round(float(boki[0]), 3),
            "krotszy_m": round(float(boki[1]), 3),
        })
    raport["warstwy"] = warstwy

    # Sama gorna powierzchnia: pas +-3 cm wokol najgestszego poziomu.
    licznik, kraw = np.histogram(wys, bins=400)
    srodki = (kraw[:-1] + kraw[1:]) / 2
    szczyt = float(srodki[np.argmax(licznik)])
    blat = (wys > szczyt - 0.03) & (wys < szczyt + 0.03)
    pole, boki = prostokat(lokalne[blat][:, :2])
    raport["gorna_powierzchnia"] = {
        "poziom_m_od_dolu": round(szczyt - dol, 3),
        "punktow": int(blat.sum()),
        "dluzszy_m": round(float(boki[0]), 3),
        "krotszy_m": round(float(boki[1]), 3),
    }
    rysuj(lokalne[blat], kolor[blat], 0, 1, katalog + "/obiekt_blat.png")
    print(json.dumps(raport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
