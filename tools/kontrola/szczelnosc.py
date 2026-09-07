"""Test szczelnosci bez zakladania, ze pokoj jest prostopadloscianem.

Poprzedni test strzelal prostopadle do scian prostopadloscianu i zglaszal
"dziury" tam, gdzie granica pokoju jest skosem - to byl artefakt testu,
nie modelu. Tutaj strzelamy z kilku punktow WEWNATRZ we wszystkie strony
po rownomiernej siatce kierunkow. Jesli powloka jest zamknieta, kazdy
promien musi cos trafic, niezaleznie od ksztaltu.

Promienie startuja 5 cm od punktu, zeby nie trafic w mebel, przy ktorym
akurat stoja - liczy sie powloka, nie wyposazenie.
"""

import json
import math
import sys

import bpy
from mathutils import Vector

bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index("--") + 1])
scene = bpy.context.scene
depsgraph = bpy.context.evaluated_depsgraph_get()

PUNKTY = [Vector(p) for p in (
    (1.45, 2.06, 1.20), (0.45, 0.60, 0.70), (2.40, 0.60, 1.60),
    (0.45, 3.60, 0.70), (2.40, 3.60, 1.60), (1.45, 2.06, 2.10),
    (1.45, 0.30, 0.30), (1.45, 3.90, 0.30),
)]

# Rownomierna siatka kierunkow metoda zlotego kata.
N = 900
zloty = math.pi * (3 - math.sqrt(5))
kierunki = []
for i in range(N):
    z = 1 - 2 * (i + 0.5) / N
    r = math.sqrt(max(0.0, 1 - z * z))
    kat = zloty * i
    kierunki.append(Vector((math.cos(kat) * r, math.sin(kat) * r, z)))

wynik = []
ucieczki = []
for punkt in PUNKTY:
    puste = 0
    for kierunek in kierunki:
        trafil, *_ = scene.ray_cast(depsgraph, punkt, kierunek, distance=12.0)
        if not trafil:
            puste += 1
            if len(ucieczki) < 20:
                ucieczki.append({
                    "z_punktu": [round(v, 2) for v in punkt],
                    "kierunek": [round(v, 3) for v in kierunek],
                })
    wynik.append({"punkt": [round(v, 2) for v in punkt],
                  "promieni": N, "ucieklo": puste,
                  "udzial": round(puste / N, 4)})

print("SZCZELNOSC2 " + json.dumps({"punkty": wynik, "przyklady": ucieczki},
                                  ensure_ascii=False))
