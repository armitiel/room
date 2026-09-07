"""Czy przy brzegach posłania naprawde jest podniesiony rant.

Na mapie wysokosci obwodka byla jasna, ale mapa pokazuje NAJWYZSZY punkt
w pikselu - przy krawedzi lapie tez to, co stoi obok lozka. Zanim wpiszemy
rant w geometrie, trzeba go zmierzyc mediana, nie maksimum.

Liczymy odleglosc kazdego punktu od brzegu prostokata posłania i median
wysokosci w pasmach co 5 cm. Jesli rant istnieje, mediana rosnie przy
brzegu; jesli to byl artefakt, mediana bedzie plaska albo opadajaca.
"""

import json
import sys

import numpy as np


def main():
    dane = np.load(sys.argv[1])
    lokalne = dane["lokalne"].astype(np.float64)
    licznik, kraw = np.histogram(lokalne[:, 2], bins=400)
    srodki = (kraw[:-1] + kraw[1:]) / 2
    szczyt = float(srodki[np.argmax(licznik)])
    blat = np.abs(lokalne[:, 2] - szczyt) < 0.04
    srodek = lokalne[blat][:, :2].mean(axis=0)

    x = lokalne[:, 0] - srodek[0]
    y = lokalne[:, 1] - srodek[1]
    z = lokalne[:, 2] - szczyt

    polowa = np.array([1.01, 0.795])       # z pomiaru materaca 2,02 x 1,59
    # Odleglosc od brzegu prostokata: ujemna na zewnatrz, dodatnia wewnatrz.
    od_brzegu = np.minimum(polowa[0] - np.abs(x), polowa[1] - np.abs(y))

    # Bierzemy tylko to, co moze byc powierzchnia posłania, zeby nie
    # wciagnac sciany ani podlogi.
    w_grze = (np.abs(z) < 0.25) & (od_brzegu > -0.12) & (od_brzegu < 0.95)

    pasma = []
    for a in np.arange(-0.10, 0.90, 0.05):
        maska = w_grze & (od_brzegu >= a) & (od_brzegu < a + 0.05)
        if maska.sum() < 200:
            pasma.append({"od_brzegu_m": round(float(a), 2),
                          "punktow": int(maska.sum())})
            continue
        pasma.append({
            "od_brzegu_m": round(float(a), 2),
            "punktow": int(maska.sum()),
            "mediana_z_m": round(float(np.median(z[maska])), 4),
            "p90_z_m": round(float(np.percentile(z[maska], 90)), 4),
            "p10_z_m": round(float(np.percentile(z[maska], 10)), 4),
        })
    print(json.dumps({"poziom_odniesienia": round(szczyt, 4),
                      "polowa_boku_m": polowa.tolist(),
                      "pasma": pasma}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
