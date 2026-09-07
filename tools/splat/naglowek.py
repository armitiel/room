"""Odczyt naglowka PLY bez zadnych zaleznosci.

Chcemy wiedziec, co ten plik naprawde zawiera, zanim cokolwiek policzymy:
ile punktow, jakie pola, jaki uklad bajtow. Splat 3DGS ma pola opacity,
scale_*, rot_* i f_dc_*; zwykla chmura z fotogrametrii ma tylko x,y,z
i kolory. To rozroznienie zmienia caly dalszy plan.
"""

import sys

path = sys.argv[1]
with open(path, "rb") as handle:
    naglowek = b""
    while b"end_header" not in naglowek and len(naglowek) < 200000:
        kawalek = handle.read(4096)
        if not kawalek:
            break
        naglowek += kawalek
    koniec = naglowek.find(b"end_header")
    tekst = naglowek[:koniec + len(b"end_header")].decode("ascii", "replace")

linie = tekst.splitlines()
print("LINII W NAGLOWKU:", len(linie))
for linia in linie[:40]:
    print(linia)
if len(linie) > 40:
    print("... (pominieto {} linii)".format(len(linie) - 40))
    for linia in linie[-5:]:
        print(linia)
print("--- offset danych:", koniec + len(b"end_header") + 1)
