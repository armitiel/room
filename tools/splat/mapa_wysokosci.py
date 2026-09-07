"""Mapa wysokosci posłania - jeden obraz zamiast dziesieciu liczb.

Podzial po kolorze pokazal kwadrat tkaniny, ale i dziure po prawej: pas
szerokosci ok. 0,3 m, w ktorym w pasie +-6 cm nie ma punktow. Nie wiadomo
z tego, czy to brak danych, czy element lezacy wyzej albo nizej.

Rzut z gory z wysokoscia zamiast koloru odpowiada na to wprost: dla kazdego
piksela najwyzszy punkt, pokolorowany wedlug wysokosci nad powierzchnia
materaca. Piksele bez zadnego punktu zostaja czarne - i wtedy widac, ze to
brak danych, a nie ksztalt.
"""

import json
import sys

import numpy as np
from PIL import Image

PX_NA_M = 250


def rampa(t):
    """Prosty gradient: granat -> turkus -> zolty -> bialy."""
    t = np.clip(t, 0.0, 1.0)
    punkty = np.array([[0.05, 0.10, 0.35], [0.10, 0.55, 0.60],
                       [0.85, 0.80, 0.25], [1.00, 1.00, 1.00]])
    pozycje = np.array([0.0, 0.4, 0.75, 1.0])
    wynik = np.zeros(t.shape + (3,))
    for i in range(3):
        wynik[..., i] = np.interp(t, pozycje, punkty[:, i])
    return wynik


def main():
    dane = np.load(sys.argv[1])
    katalog = sys.argv[2]
    lokalne = dane["lokalne"].astype(np.float64)
    wys = lokalne[:, 2]
    licznik, kraw = np.histogram(wys, bins=400)
    srodki = (kraw[:-1] + kraw[1:]) / 2
    szczyt = float(srodki[np.argmax(licznik)])

    blat = np.abs(wys - szczyt) < 0.04
    srodek = lokalne[blat][:, :2].mean(axis=0)
    polowa = np.array([1.25, 1.10])
    w_kadrze = np.all(np.abs(lokalne[:, :2] - srodek) < polowa, axis=1)

    p = lokalne[w_kadrze][:, :2] - srodek
    h = wys[w_kadrze] - szczyt

    szer = int(2 * polowa[0] * PX_NA_M)
    wysk = int(2 * polowa[1] * PX_NA_M)
    px = ((p[:, 0] + polowa[0]) / (2 * polowa[0]) * (szer - 1)).astype(np.int32)
    py = wysk - 1 - ((p[:, 1] + polowa[1]) / (2 * polowa[1]) * (wysk - 1)).astype(np.int32)

    mapa = np.full((wysk, szer), -np.inf)
    np.maximum.at(mapa, (py, px), h)
    trafione = np.isfinite(mapa)

    dolny, gorny = -0.10, 0.35
    znorm = (np.clip(mapa, dolny, gorny) - dolny) / (gorny - dolny)
    obraz = rampa(np.where(trafione, znorm, 0.0))
    obraz[~trafione] = 0.0
    Image.fromarray((obraz * 255).astype(np.uint8)).save(katalog + "/mapa_wysokosci.png")

    # Profil wzdluz dlugosci: mediana wysokosci w kolumnach pikseli.
    profil = []
    for i in range(0, szer, max(1, szer // 25)):
        kolumna = mapa[:, i]
        wartosci = kolumna[np.isfinite(kolumna)]
        profil.append({
            "x_od_srodka_m": round(float(-polowa[0] + 2 * polowa[0] * i / (szer - 1)), 3),
            "pikseli": int(wartosci.size),
            "mediana_m": round(float(np.median(wartosci)), 3) if wartosci.size else None,
            "max_m": round(float(wartosci.max()), 3) if wartosci.size else None,
        })

    print(json.dumps({
        "poziom_materaca": round(szczyt, 4),
        "kadr_m": [round(2 * polowa[0], 2), round(2 * polowa[1], 2)],
        "pikseli": [szer, wysk],
        "pokrycie": round(float(trafione.mean()), 3),
        "skala_koloru_m": [dolny, gorny],
        "profil_wzdluz": profil,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
