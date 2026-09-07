"""Ile mierzy sama narzuta z mandala, a ile calosc poslania.

Profil gestosci pokazal cos, czego percentyl nie widzial: rdzen gornej
powierzchni jest niemal kwadratowy (1,63 x 1,58 m), a do 2,0 m siega tylko
rzadsza obwodka. To znaczy, ze na lozku lezy kwadratowa tkanina, a nie ze
lozko jest kwadratowe. Zeby to rozstrzygnac, dzielimy punkty po kolorze:
tkanina jest chlodna (niebieski nie mniejszy od czerwonego), podloga
i jasny pas sa cieple.

Wynik: osobny prostokat dla tkaniny i osobny dla reszty.
"""

import json
import sys

import numpy as np
from PIL import Image


def prostokat(p, krok=0.1):
    najlepszy = None
    for kat in np.arange(0.0, 90.0, krok):
        r = np.radians(kat)
        c, s = np.cos(r), np.sin(r)
        obr = p @ np.array([[c, -s], [s, c]])
        dol = np.percentile(obr, 1.0, axis=0)
        gora = np.percentile(obr, 99.0, axis=0)
        boki = gora - dol
        if najlepszy is None or boki[0] * boki[1] < najlepszy[0]:
            najlepszy = (float(boki[0] * boki[1]), float(kat), boki.copy())
    boki = np.sort(najlepszy[2])[::-1]
    return {"dluzszy_m": round(float(boki[0]), 3),
            "krotszy_m": round(float(boki[1]), 3),
            "proporcja": round(float(boki[0] / boki[1]), 4),
            "pole_m2": round(najlepszy[0], 3),
            "kat_stopnie": round(najlepszy[1], 2)}


def main():
    dane = np.load(sys.argv[1])
    katalog = sys.argv[2]
    lokalne = dane["lokalne"].astype(np.float64)
    kolor = dane["kolor"].astype(np.float64)
    wys = lokalne[:, 2]

    licznik, kraw = np.histogram(wys, bins=400)
    srodki = (kraw[:-1] + kraw[1:]) / 2
    szczyt = float(srodki[np.argmax(licznik)])
    pas = np.abs(wys - szczyt) < 0.06

    p = lokalne[pas][:, :2]
    b = kolor[pas]
    chlodne = (b[:, 2] - b[:, 0]) > 0.02

    raport = {
        "punktow_w_pasie": int(pas.sum()),
        "udzial_tkaniny": round(float(chlodne.mean()), 3),
        "tkanina_z_mandala": prostokat(p[chlodne]),
        "reszta_pasa": prostokat(p[~chlodne]) if (~chlodne).sum() > 500 else None,
        "caly_pas": prostokat(p),
        "kolor_tkaniny": "#%02x%02x%02x" % tuple((b[chlodne].mean(axis=0) * 255).astype(int)),
        "kolor_reszty": "#%02x%02x%02x" % tuple((b[~chlodne].mean(axis=0) * 255).astype(int)),
    }

    # Podglad podzialu: tkanina na niebiesko, reszta na pomaranczowo.
    rozmiar = 900
    dol = p.min(axis=0)
    zakres = (p.max(axis=0) - dol).max() * 1.05
    px = ((p[:, 0] - dol[0]) / zakres * (rozmiar - 1)).astype(np.int32)
    py = rozmiar - 1 - ((p[:, 1] - dol[1]) / zakres * (rozmiar - 1)).astype(np.int32)
    ok = (px >= 0) & (px < rozmiar) & (py >= 0) & (py < rozmiar)
    obraz = np.full((rozmiar, rozmiar, 3), 16, dtype=np.uint8)
    obraz[py[ok & ~chlodne], px[ok & ~chlodne]] = (230, 140, 40)
    obraz[py[ok & chlodne], px[ok & chlodne]] = (60, 150, 230)
    Image.fromarray(obraz).save(katalog + "/podzial_tkanina.png")
    raport["px_na_m_podgladu"] = round(float(rozmiar / zakres), 1)
    print(json.dumps(raport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
