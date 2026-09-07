"""Pomiar obiektu ze splata: orientacja, prostokat opisujacy, wysokosci.

Skan obejmuje jeden przedmiot (99% punktow w promieniu 2 m od srodka),
lezacy skosnie wzgledem osi pliku. Pudelko rownolegle do osi zawyzaloby
wymiary o kilkanascie procent, wiec:

1. PCA na chmurze - najmniejszy wektor wlasny plaskiej plyty to jej normalna,
   czyli kierunek "w gore". Nie zakladamy, ktora os pliku jest pionowa.
2. Obrot do ukladu obiektu, potem przemiatanie katem co 0.25 stopnia
   i wybor prostokata o najmniejszym polu - to daje dlugosc i szerokosc.
3. Histogram wysokosci wzgledem plaszczyzny bazowej - grubosc, poziom
   blatu/materaca i to, co wystaje ponad.

Skala pliku jest przyjeta bez dowodu: 3DGS z samych zdjec jej nie ma.
Dlatego raport podaje wymiary i osobno wprost mowi, czym je zweryfikowac.
"""

import json
import sys

import numpy as np


def wczytaj(sciezka, promien, prog_krycia=0.4, max_promien=0.5):
    dane = np.load(sciezka)
    xyz = dane["xyz"].astype(np.float64)
    maska = (dane["krycie"] > prog_krycia) & (dane["promien"].max(axis=1) < max_promien)
    srodek = np.median(xyz[maska], axis=0)
    blisko = maska & (np.linalg.norm(xyz - srodek, axis=1) < promien)
    return xyz[blisko], dane["kolor"][blisko], dane["krycie"][blisko]


def uklad_obiektu(punkty):
    """Zwraca (srodek, macierz 3x3), gdzie trzeci wiersz to normalna plyty."""
    srodek = punkty.mean(axis=0)
    przesuniete = punkty - srodek
    kowariancja = przesuniete.T @ przesuniete / len(przesuniete)
    wartosci, wektory = np.linalg.eigh(kowariancja)
    kolejnosc = np.argsort(wartosci)[::-1]          # od najwiekszej
    wektory = wektory[:, kolejnosc]
    baza = np.stack([wektory[:, 0], wektory[:, 1], wektory[:, 2]])
    if np.linalg.det(baza) < 0:
        baza[2] *= -1
    return srodek, baza, np.sqrt(wartosci[kolejnosc])


def najmniejszy_prostokat(punkty_2d, krok_stopnie=0.25):
    najlepsze = None
    for kat in np.arange(0.0, 90.0, krok_stopnie):
        radiany = np.radians(kat)
        c, s = np.cos(radiany), np.sin(radiany)
        obrocone = punkty_2d @ np.array([[c, -s], [s, c]])
        dol = np.percentile(obrocone, 0.5, axis=0)
        gora = np.percentile(obrocone, 99.5, axis=0)
        boki = gora - dol
        pole = boki[0] * boki[1]
        if najlepsze is None or pole < najlepsze[0]:
            najlepsze = (pole, kat, boki.copy(), dol.copy(), gora.copy())
    return najlepsze


def main():
    npz, promien = sys.argv[1], float(sys.argv[2])
    punkty, kolory, krycie = wczytaj(npz, promien)
    srodek, baza, sigma = uklad_obiektu(punkty)
    lokalne = (punkty - srodek) @ baza.T          # kolumny: dlugi, sredni, cienki

    raport = {
        "punktow": int(len(punkty)),
        "promien_ciecia_m": promien,
        "odchylenia_glowne_m": sigma.round(4).tolist(),
        "normalna_plyty_w_osiach_pliku": baza[2].round(4).tolist(),
    }

    # Plaszczyzna bazowa: najgestszy poziom wzdluz normalnej to gorna
    # powierzchnia. Dol bierzemy z 1. percentyla, zeby nie liczyc szumu.
    wysokosc = lokalne[:, 2]
    licznik, krawedzie = np.histogram(wysokosc, bins=400)
    srodki = (krawedzie[:-1] + krawedzie[1:]) / 2
    dominujaca = float(srodki[np.argmax(licznik)])
    dol = float(np.percentile(wysokosc, 0.5))
    gora = float(np.percentile(wysokosc, 99.5))
    raport["wysokosc"] = {
        "dol_m": round(dol, 4), "gora_m": round(gora, 4),
        "grubosc_m": round(gora - dol, 4),
        "najgestszy_poziom_m": round(dominujaca, 4),
        "od_dolu_do_najgestszego_m": round(dominujaca - dol, 4),
    }

    najlepsze = najmniejszy_prostokat(lokalne[:, :2])
    pole, kat, boki, d, g = najlepsze
    boki = np.sort(boki)[::-1]
    raport["prostokat"] = {
        "dluzszy_bok_m": round(float(boki[0]), 4),
        "krotszy_bok_m": round(float(boki[1]), 4),
        "pole_m2": round(float(pole), 4),
        "kat_obrotu_stopnie": round(float(kat), 2),
        "proporcja": round(float(boki[0] / boki[1]), 3),
    }

    # Profil: ile punktow na kolejnych warstwach wysokosci.
    warstwy = []
    for i in range(0, 20):
        a = dol + (gora - dol) * i / 20.0
        b = dol + (gora - dol) * (i + 1) / 20.0
        ile = int(np.count_nonzero((wysokosc >= a) & (wysokosc < b)))
        warstwy.append({"od_m": round(a - dol, 3), "do_m": round(b - dol, 3),
                        "punktow": ile})
    raport["profil_wysokosci"] = warstwy

    np.savez_compressed(npz.replace(".npz", "_lokalne.npz"),
                        lokalne=lokalne.astype(np.float32),
                        kolor=kolory.astype(np.float32),
                        krycie=krycie.astype(np.float32),
                        srodek=srodek, baza=baza)
    print(json.dumps(raport, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
