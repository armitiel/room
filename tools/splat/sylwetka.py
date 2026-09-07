"""Sylwetka gestosci w przekroju - mocniejsza niz rozrzut kolorow.

Punkty pomalowane wlasnym kolorem gina na czarnym tle, kiedy jest ich malo.
Tutaj kazda komorka przekroju dostaje jasnosc od LICZBY punktow (skala
logarytmiczna), wiec cienka, ale gesta scianka zaglowka widac tak samo
dobrze jak rozmyta chmure nad lozkiem.

Trzy przekroje: przez cala szerokosc lozka, przez lewa polowe i przez prawa.
Jesli zaglowek istnieje, w kazdym z nich stoi w tym samym miejscu.
"""

import json
import sys

import numpy as np
from PIL import Image

PX_NA_M = 400
X_OD, X_DO = -1.5, 1.5
Z_OD, Z_DO = -0.5, 1.2


def sylwetka(x, z, sciezka):
    szer = int((X_DO - X_OD) * PX_NA_M)
    wysk = int((Z_DO - Z_OD) * PX_NA_M)
    px = ((x - X_OD) * PX_NA_M).astype(np.int32)
    pz = wysk - 1 - ((z - Z_OD) * PX_NA_M).astype(np.int32)
    ok = (px >= 0) & (px < szer) & (pz >= 0) & (pz < wysk)
    licznik = np.zeros((wysk, szer), dtype=np.float64)
    np.add.at(licznik, (pz[ok], px[ok]), 1.0)
    jasnosc = np.log1p(licznik)
    if jasnosc.max() > 0:
        jasnosc = jasnosc / jasnosc.max()
    obraz = (np.clip(jasnosc, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(np.dstack([obraz] * 3)).save(sciezka)
    return {"px": [szer, wysk], "max_w_komorce": int(licznik.max())}


def main():
    dane = np.load(sys.argv[1])
    katalog = sys.argv[2]
    lokalne = dane["lokalne"].astype(np.float64)
    licznik, kraw = np.histogram(lokalne[:, 2], bins=400)
    srodki = (kraw[:-1] + kraw[1:]) / 2
    szczyt = float(srodki[np.argmax(licznik)])
    blat = np.abs(lokalne[:, 2] - szczyt) < 0.04
    srodek = lokalne[blat][:, :2].mean(axis=0)

    x = lokalne[:, 0] - srodek[0]
    y = lokalne[:, 1] - srodek[1]
    z = lokalne[:, 2] - szczyt

    raport = {"skala_px_na_m": PX_NA_M, "zakres_x": [X_OD, X_DO],
              "zakres_z": [Z_OD, Z_DO]}
    raport["calosc"] = sylwetka(x, z, katalog + "/sylwetka_x.png")
    lewa = y < 0
    raport["lewa_polowa"] = sylwetka(x[lewa], z[lewa], katalog + "/sylwetka_x_lewa.png")
    raport["prawa_polowa"] = sylwetka(x[~lewa], z[~lewa], katalog + "/sylwetka_x_prawa.png")
    # Przekroj w poprzek lozka - pokaze boki i ewentualne rantu.
    szer = int((X_DO - X_OD) * PX_NA_M)
    wysk = int((Z_DO - Z_OD) * PX_NA_M)
    px = ((y - X_OD) * PX_NA_M).astype(np.int32)
    pz = wysk - 1 - ((z - Z_OD) * PX_NA_M).astype(np.int32)
    ok = (px >= 0) & (px < szer) & (pz >= 0) & (pz < wysk)
    licz = np.zeros((wysk, szer))
    np.add.at(licz, (pz[ok], px[ok]), 1.0)
    j = np.log1p(licz)
    j = j / max(j.max(), 1e-9)
    Image.fromarray(np.dstack([(j * 255).astype(np.uint8)] * 3)).save(
        katalog + "/sylwetka_y.png")

    print(json.dumps(raport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
