"""Proporcje posłania liczone kilkoma niezaleznymi definicjami krawedzi.

Percentyl 0,5/99,5 to wygodna, ale arbitralna definicja brzegu. Jesli
proporcja ma byc argumentem za zmiana modelu, musi wyjsc tak samo przy
kilku sposobach liczenia. Dlatego tutaj krawedz wyznacza spadek gestosci:
profil punktow co 5 mm, a brzeg tam, gdzie gestosc spada do polowy
(albo 10% / 90%) poziomu plateau.

Dodatkowo porownanie z typowymi rozmiarami materacy.
"""

import json
import sys

import numpy as np

TYPOWE = {
    "200x160": 2.00 / 1.60, "200x180": 2.00 / 1.80, "200x140": 2.00 / 1.40,
    "200x120": 2.00 / 1.20, "190x160": 1.90 / 1.60, "210x160": 2.10 / 1.60,
    "200x150": 2.00 / 1.50, "220x160": 2.20 / 1.60,
}


def krawedzie(wartosci, udzial):
    licznik, kraw = np.histogram(wartosci, bins=np.arange(
        wartosci.min(), wartosci.max() + 0.005, 0.005))
    srodki = (kraw[:-1] + kraw[1:]) / 2
    plateau = np.percentile(licznik[licznik > 0], 75)
    prog = plateau * udzial
    nad = np.flatnonzero(licznik >= prog)
    if len(nad) < 2:
        return None
    return float(srodki[nad[0]]), float(srodki[nad[-1]])


def main():
    dane = np.load(sys.argv[1])
    lokalne = dane["lokalne"].astype(np.float64)
    wys = lokalne[:, 2]
    licznik, kraw = np.histogram(wys, bins=400)
    srodki = (kraw[:-1] + kraw[1:]) / 2
    szczyt = float(srodki[np.argmax(licznik)])

    wynik = {"poziom_odniesienia": round(szczyt, 4), "definicje": {}}

    for nazwa, pas in (("blat +-3cm", 0.03), ("blat +-6cm", 0.06)):
        maska = np.abs(wys - szczyt) < pas
        p = lokalne[maska][:, :2]
        # Najlepszy kat: minimalne pole prostokata.
        najlepszy = None
        for kat in np.arange(0.0, 90.0, 0.1):
            r = np.radians(kat)
            c, s = np.cos(r), np.sin(r)
            obr = p @ np.array([[c, -s], [s, c]])
            boki = np.percentile(obr, 99.5, axis=0) - np.percentile(obr, 0.5, axis=0)
            if najlepszy is None or boki[0] * boki[1] < najlepszy[0]:
                najlepszy = (boki[0] * boki[1], kat)
        kat = najlepszy[1]
        r = np.radians(kat)
        c, s = np.cos(r), np.sin(r)
        obr = p @ np.array([[c, -s], [s, c]])

        opis = {"punktow": int(maska.sum()), "kat_stopnie": round(float(kat), 2)}
        for etykieta, udzial in (("percentyl_0.5_99.5", None),
                                 ("gestosc_10%", 0.10),
                                 ("gestosc_50%", 0.50),
                                 ("gestosc_90%", 0.90)):
            if udzial is None:
                boki = np.percentile(obr, 99.5, axis=0) - np.percentile(obr, 0.5, axis=0)
            else:
                a = krawedzie(obr[:, 0], udzial)
                b = krawedzie(obr[:, 1], udzial)
                if a is None or b is None:
                    continue
                boki = np.array([a[1] - a[0], b[1] - b[0]])
            dluz, krot = float(max(boki)), float(min(boki))
            opis[etykieta] = {
                "dluzszy_m": round(dluz, 3), "krotszy_m": round(krot, 3),
                "proporcja": round(dluz / krot, 4),
            }
        wynik["definicje"][nazwa] = opis

    wzorzec = wynik["definicje"]["blat +-3cm"]["gestosc_50%"]["proporcja"]
    wynik["model_w_projekcie"] = {
        "mattress_2.02x1.61": round(2.02 / 1.61, 4),
        "baza_2.05x1.66": round(2.05 / 1.66, 4),
    }
    wynik["dopasowanie_do_typowych"] = {
        k: round(abs(v - wzorzec), 4) for k, v in
        sorted(TYPOWE.items(), key=lambda kv: abs(kv[1] - wzorzec))
    }
    print(json.dumps(wynik, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
