"""Pierwsze spojrzenie na splat: co tam w ogole jest.

Wczytuje tylko te kolumny, ktore sa potrzebne do geometrii i koloru
(polozenie, krycie, rozmiar, skladowa stala harmonicznych), a 45 kolumn
f_rest_* pomija - to 72% pliku i nie mowi nic o wymiarach.

Wynik zapisuje jako .npz, zeby kolejne kroki nie parsowaly 94 MB od nowa.
"""

import json
import sys

import numpy as np

C0 = 0.28209479177387814  # skladowa stala harmonicznych sferycznych


def czytaj_naglowek(path):
    with open(path, "rb") as handle:
        surowy = b""
        while b"end_header" not in surowy and len(surowy) < 200000:
            surowy += handle.read(4096)
        koniec = surowy.find(b"end_header") + len(b"end_header")
        tekst = surowy[:koniec].decode("ascii", "replace")
    offset = koniec + 1
    if surowy[koniec:koniec + 2] == b"\r\n":
        offset = koniec + 2
    pola = []
    liczba = 0
    for linia in tekst.splitlines():
        czesci = linia.split()
        if not czesci:
            continue
        if czesci[0] == "element" and czesci[1] == "vertex":
            liczba = int(czesci[2])
        elif czesci[0] == "property":
            if czesci[1] != "float":
                raise SystemExit("Nieobslugiwany typ pola: " + linia)
            pola.append(czesci[2])
    return pola, liczba, offset


def main():
    path = sys.argv[1]
    wyjscie = sys.argv[2]
    pola, liczba, offset = czytaj_naglowek(path)
    dane = np.memmap(path, dtype=np.float32, mode="r", offset=offset,
                     shape=(liczba, len(pola)))
    idx = {nazwa: i for i, nazwa in enumerate(pola)}

    xyz = np.array(dane[:, [idx["x"], idx["y"], idx["z"]]], dtype=np.float64)
    opacity = np.array(dane[:, idx["opacity"]], dtype=np.float64)
    skala = np.array(dane[:, [idx["scale_0"], idx["scale_1"], idx["scale_2"]]],
                     dtype=np.float64)
    dc = np.array(dane[:, [idx["f_dc_0"], idx["f_dc_1"], idx["f_dc_2"]]],
                  dtype=np.float64)

    krycie = 1.0 / (1.0 + np.exp(-opacity))          # sigmoida, jak w 3DGS
    promien = np.exp(skala)                           # log-skala -> metry
    kolor = np.clip(0.5 + C0 * dc, 0.0, 1.0)

    raport = {
        "plik": path,
        "gaussianow": int(liczba),
        "pol_na_punkt": len(pola),
        "ma_sh": sum(1 for p in pola if p.startswith("f_rest_")),
        "bbox_min": xyz.min(axis=0).round(3).tolist(),
        "bbox_max": xyz.max(axis=0).round(3).tolist(),
        "rozpietosc": (xyz.max(axis=0) - xyz.min(axis=0)).round(3).tolist(),
        "krycie_percentyle": np.percentile(krycie, [5, 25, 50, 75, 95]).round(3).tolist(),
        "promien_percentyle_m": np.percentile(promien.max(axis=1),
                                              [5, 50, 95, 99]).round(4).tolist(),
        "srodek_masy": xyz.mean(axis=0).round(3).tolist(),
    }

    # Ktora os jest pionowa? Podloga i sufit to dwie gigantyczne plaszczyzny,
    # wiec wzdluz osi pionowej histogram ma dwa ostre szczyty, a wzdluz
    # poziomych rozklad jest rozmyty. Liczymy udzial najgestszego przedzialu.
    ostrosc = []
    for os_ in range(3):
        wartosci = xyz[krycie > 0.5, os_]
        if wartosci.size == 0:
            wartosci = xyz[:, os_]
        licznik, _ = np.histogram(wartosci, bins=200)
        ostrosc.append(float(licznik.max() / max(licznik.sum(), 1)))
    raport["skupienie_na_osi"] = [round(v, 4) for v in ostrosc]
    raport["os_pionowa_zgadywana"] = int(np.argmax(ostrosc))

    np.savez_compressed(wyjscie, xyz=xyz.astype(np.float32),
                        krycie=krycie.astype(np.float32),
                        promien=promien.astype(np.float32),
                        kolor=kolor.astype(np.float32))
    print(json.dumps(raport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
