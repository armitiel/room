"""Zaglowek: gdzie sie zaczyna, jak gruby, jak wysoki.

Poprzednie podejscie brало wszystko powyzej 40 cm nad materacem i wyszedl
smietnik - punkty siegaly +-1,4 m, czyli obejmowaly pol pokoju. Tym razem
patrzymy waskim pasem przez srodek lozka i w przekroju pionowym, gdzie
zaglowek jest po prostu pionowa scianka tuz za krawedzia materaca.

Kryterium rozdzielenia zaglowka od sciany za nim: zaglowek jest grubszy
(odstaje od plaszczyzny sciany) i konczy sie pozioma krawedzia, powyzej
ktorej zostaje juz tylko cienka plaszczyzna sciany.
"""

import json
import sys

import numpy as np
from PIL import Image

PX_NA_M = 420


def przekroj(punkty, barwy, sciezka, zakres_x, zakres_z):
    szer = int((zakres_x[1] - zakres_x[0]) * PX_NA_M)
    wysk = int((zakres_z[1] - zakres_z[0]) * PX_NA_M)
    px = ((punkty[:, 0] - zakres_x[0]) * PX_NA_M).astype(np.int32)
    pz = wysk - 1 - ((punkty[:, 1] - zakres_z[0]) * PX_NA_M).astype(np.int32)
    ok = (px >= 0) & (px < szer) & (pz >= 0) & (pz < wysk)
    obraz = np.full((wysk, szer, 3), 16, dtype=np.uint8)
    obraz[pz[ok], px[ok]] = (barwy[ok] * 255).astype(np.uint8)
    Image.fromarray(obraz).save(sciezka)
    return [szer, wysk]


def main():
    dane = np.load(sys.argv[1])
    katalog = sys.argv[2]
    lokalne = dane["lokalne"].astype(np.float64)
    kolor = dane["kolor"].astype(np.float64)

    licznik, kraw = np.histogram(lokalne[:, 2], bins=400)
    srodki = (kraw[:-1] + kraw[1:]) / 2
    szczyt = float(srodki[np.argmax(licznik)])

    blat = np.abs(lokalne[:, 2] - szczyt) < 0.04
    srodek = lokalne[blat][:, :2].mean(axis=0)
    x = lokalne[:, 0] - srodek[0]
    y = lokalne[:, 1] - srodek[1]
    z = lokalne[:, 2] - szczyt

    raport = {"krawedz_materaca_m": 1.01}

    # Przekroj pionowy przez srodek lozka.
    pas = np.abs(y) < 0.55
    raport["przekroj_px"] = przekroj(
        np.c_[x[pas], z[pas]], kolor[pas], katalog + "/przekroj_wzdluz.png",
        (-1.45, 1.45), (-0.45, 1.05))

    for nazwa, wybor in (("koniec_plus", x > 0.95), ("koniec_minus", x < -0.95)):
        maska = wybor & (np.abs(y) < 0.85) & (z > -0.15) & (z < 1.2)
        opis = {"punktow": int(maska.sum())}
        if maska.sum() > 300:
            zz = z[maska]
            xx = x[maska]
            # Rozklad wysokosci co 5 cm - gdzie konczy sie gesta scianka.
            poziomy = []
            for prog in np.arange(0.0, 1.05, 0.05):
                w = (zz >= prog) & (zz < prog + 0.05)
                if w.sum() < 20:
                    poziomy.append({"z_m": round(float(prog), 2), "punktow": int(w.sum())})
                    continue
                poziomy.append({
                    "z_m": round(float(prog), 2),
                    "punktow": int(w.sum()),
                    "x_od_do_m": [round(float(np.percentile(xx[w], 5)), 3),
                                  round(float(np.percentile(xx[w], 95)), 3)],
                    "grubosc_m": round(float(np.percentile(xx[w], 95)
                                             - np.percentile(xx[w], 5)), 3),
                    "szerokosc_y_m": round(float(np.percentile(y[maska][w], 95)
                                                 - np.percentile(y[maska][w], 5)), 3),
                })
            opis["po_wysokosci"] = poziomy
        raport[nazwa] = opis

    print(json.dumps(raport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
