"""v06: poprawki lozka wynikajace ze skanu gaussowskiego work/Osowa.ply.

Co i dlaczego - kazda zmiana ma za soba pomiar, nie wrazenie:

1. Oparcie bylo grubsze i wyzsze niz w rzeczywistosci. W skanie pionowa
   scianka przy krawedzi materaca ma w dolnych 15 cm **6-9 cm** gruboscl,
   a liczba punktow zalamuje sie miedzy 0,40 a 0,45 m nad materacem
   (4806 -> 48 punktow na 5 cm). Model mial 0,14 m grubosci i gorna
   krawedz 0,59 m nad materacem. Nowe: 0,09 m i 0,45 m.

2. Kołdra byla szersza od lozka. Model: 1,77 m przy bazie 1,66 m, czyli
   5,5 cm zwisu z kazdej strony. Skan: pokrycie konczy sie na krawedzi,
   caly obrys z rantem to ok. 2,12 x 1,68 m. Nowe: 1,68 m, a zejscie
   tkaniny skrocone z 8 do 3,5 cm, wiec opada przy samej krawedzi.

3. Materac 2,02 x 1,61 zostaje. Skan mierzy powierzchnie spod tkaniny na
   2,02 x 1,59 - to potwierdzenie, nie poprawka. Zmienia sie tylko status
   w zapisie pomiarow: bylo "oszacowane ze zdjec", jest "zmierzone".

Czego NIE zmieniam, choc bylo w planie: podniesionego rantu przy brzegach.
Na mapie wysokosci obwodka wygladala na wyzsza, ale mapa pokazuje najwyzszy
punkt w pikselu. Mediana liczona pasmami od brzegu nie potwierdza rantu -
wychodzi plasko z rozrzutem +-8 cm. Zmierzone i odrzucone.

Opcjonalnie (--narzuta): kwadratowa narzuta 1,72 x 1,60 m z tekstura
z ortofoto skanu. Domyslnie wylaczona, bo to zmiana wygladu, a nie wymiaru
- model odwzorowuje pokoj ze zdjec z 6 wrzesnia, gdzie lezy prazkowana
poscie, a nie mandala.

Uruchomienie:
    blender --background --python blender/scripts/refine_bed_v06.py
    blender --background --python blender/scripts/refine_bed_v06.py -- --narzuta
"""

import json
import math
import sys

import bpy
from pathlib import Path

ROOT = Path(r"C:\Users\DELL\Room")
ZRODLO = ROOT / "work/scenes/attic-room-v05/Room-attic-v05.blend"
OUT = ROOT / "work/scenes/attic-room-v06"
TEKSTURA = ROOT / "work/scan/narzuta_tekstura_1987x1578mm.png"

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
Z_NARZUTA = "--narzuta" in ARGS

# Pomiary ze skanu, w metrach. Poziom odniesienia: wierzch materaca.
OPARCIE_GRUBOSC = 0.09
OPARCIE_NAD_MATERACEM = 0.45
KOLDRA_SZEROKOSC = 1.68
NARZUTA = (1.72, 1.60)

MATERAC_WIERZCH = 0.555          # 0,44 srodek + 0,115 polowa wysokosci
OPARCIE_DOL = 0.095              # jak w v04, panel stoi na podlodze
OPARCIE_TYL_X = 2.87             # tylna plaszczyzna panelu, bez zmian
KOLDRA_SRODEK_Y = 2.92
MATERAC_Y = (2.115, 3.725)


bpy.ops.wm.open_mainfile(filepath=str(ZRODLO))
scene = bpy.context.scene
OUT.mkdir(parents=True, exist_ok=True)

przed = {}
for nazwa in ("Headboard padded panel", "Draped striped duvet", "Mattress"):
    obiekt = bpy.data.objects.get(nazwa)
    if obiekt:
        przed[nazwa] = [round(v, 4) for v in obiekt.dimensions]


def usun(prefiksy):
    for obiekt in list(bpy.data.objects):
        if obiekt.name.startswith(prefiksy):
            bpy.data.objects.remove(obiekt, do_unlink=True)


def box(name, loc, size, material, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obiekt = bpy.context.object
    obiekt.name = name
    obiekt.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obiekt.data.materials.append(material)
    if bevel:
        mod = obiekt.modifiers.new("Soft formed edges", "BEVEL")
        mod.width = bevel
        mod.segments = 4
        obiekt.modifiers.new("Weighted corner normals", "WEIGHTED_NORMAL")
    return obiekt


def mesh(name, verts, faces, material, uvs=None):
    dane = bpy.data.meshes.new(name)
    dane.from_pydata(verts, [], faces)
    dane.update()
    if uvs:
        warstwa = dane.uv_layers.new()
        for poly in dane.polygons:
            for li in poly.loop_indices:
                warstwa.data[li].uv = uvs[dane.loops[li].vertex_index]
    obiekt = bpy.data.objects.new(name, dane)
    bpy.context.collection.objects.link(obiekt)
    if material:
        dane.materials.append(material)
    return obiekt


# --- 1. Oparcie ---------------------------------------------------------
tapicerka = bpy.data.materials.get("Bed upholstery weave") or \
    bpy.data.materials.get("Grey upholstered bed")
if tapicerka is None:
    tapicerka = next(m for m in bpy.data.materials if "uphol" in m.name.lower())

usun(("Headboard padded panel",))
wysokosc = MATERAC_WIERZCH + OPARCIE_NAD_MATERACEM - OPARCIE_DOL
srodek_x = OPARCIE_TYL_X - OPARCIE_GRUBOSC / 2
for y in (2.49, 3.35):
    box("Headboard padded panel", (srodek_x, y, OPARCIE_DOL + wysokosc / 2),
        (OPARCIE_GRUBOSC, 0.848, wysokosc), tapicerka, 0.022)


# --- 2. Koldra ----------------------------------------------------------
posciel = bpy.data.objects["Draped striped duvet"].data.materials[0]
usun(("Draped striped duvet",))

y0 = KOLDRA_SRODEK_Y - KOLDRA_SZEROKOSC / 2
zejscie = MATERAC_Y[0] - y0          # ile tkaniny zostaje poza materacem
verts, faces, uvs = [], [], []
nx, ny = 144, 112
for i in range(nx + 1):
    for j in range(ny + 1):
        u = i / nx
        v = j / ny
        x = 0.70 + 2.08 * u
        y = y0 + KOLDRA_SZEROKOSC * v
        # Zejscie tkaniny liczone od krawedzi materaca, a nie od srodka -
        # dzieki temu przy weszej koldrze opada tuz przy krawedzi lozka.
        brzeg = max(0.0, (0.79 - x) / 0.09,
                    (MATERAC_Y[0] - y) / zejscie,
                    (y - MATERAC_Y[1]) / zejscie)
        z = 0.574 - 0.17 * min(brzeg, 1.0) ** 1.7
        koperta = math.exp(-((x - 1.78) / 0.58) ** 2 - ((y - 2.94) / 0.60) ** 2)
        z += koperta * (0.017 * math.sin(41 * x + 18 * y + 1.8 * math.sin(13 * y))
                        + 0.011 * math.sin(69 * x - 23 * y + 2 * math.sin(11 * x))
                        + 0.005 * math.sin(112 * x + 53 * y))
        z += 0.012 * math.sin(y * 28 + x * 6) * math.exp(-((x - 0.9) / 0.26) ** 2)
        verts.append((x, y, z))
        uvs.append((v, u))
for i in range(nx):
    for j in range(ny):
        a = i * (ny + 1) + j
        faces.append((a, a + ny + 1, a + ny + 2, a + 1))
koldra = mesh("Draped striped duvet", verts, faces, posciel, uvs)
for poly in koldra.data.polygons:
    poly.use_smooth = True
sol = koldra.modifiers.new("Fabric thickness", "SOLIDIFY")
sol.thickness = 0.002

# --- 3. Narzuta z mandala (opcjonalnie) ---------------------------------
narzuta_dodana = False
if Z_NARZUTA and TEKSTURA.exists():
    material = bpy.data.materials.new("Mandala throw")
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    obraz = material.node_tree.nodes.new("ShaderNodeTexImage")
    obraz.image = bpy.data.images.load(str(TEKSTURA))
    material.node_tree.links.new(bsdf.inputs["Base Color"], obraz.outputs["Color"])
    bsdf.inputs["Roughness"].default_value = 0.78

    nx2, ny2 = 96, 88
    verts2, faces2, uvs2 = [], [], []
    for i in range(nx2 + 1):
        for j in range(ny2 + 1):
            u = i / nx2
            v = j / ny2
            x = 1.78 - NARZUTA[0] / 2 + NARZUTA[0] * u
            y = KOLDRA_SRODEK_Y - NARZUTA[1] / 2 + NARZUTA[1] * v
            z = 0.578 + 0.006 * math.sin(9 * x + 5 * y) - \
                0.05 * max(0.0, (0.06 - min(u, 1 - u, v, 1 - v)) / 0.06) ** 1.6
            verts2.append((x, y, z))
            uvs2.append((u, v))
    for i in range(nx2):
        for j in range(ny2):
            a = i * (ny2 + 1) + j
            faces2.append((a, a + ny2 + 1, a + ny2 + 2, a + 1))
    narzuta = mesh("Mandala throw", verts2, faces2, material, uvs2)
    for poly in narzuta.data.polygons:
        poly.use_smooth = True
    narzuta.modifiers.new("Fabric thickness", "SOLIDIFY").thickness = 0.003
    narzuta_dodana = True


# --- 4. Uszczelnienie powloki -------------------------------------------
# W Unrealu widac bylo swiatlo w narozach. Powod znaleziony w geometrii:
# "Entrance end wall" i "Window end left" to plaszczyzny o ZEROWEJ
# gruboscl (y 0..0 oraz 4,12..4,12), a wszystkie styki scian sa dokladne,
# bez zakladki. Rasteryzator Blendera tego nie pokazuje, Lumen owszem:
# jednostronna plaszczyzna nie ma czego zapisac w cache powierzchni, wiec
# slonce przechodzi przez nia wprost, a styk bez zakladki jest szczelina
# o szerokosci bledu zaokraglenia.
#
# Wszystkie poprawki ida NA ZEWNATRZ i W DOL. Zadne lico od strony wnetrza
# sie nie rusza, wiec zaden wymiar pokoju sie nie zmienia.
#
# Czego swiadomie nie ruszam: bryly sciany szczytowej stoja okrakiem na
# krawedzi podlogi (y 4,06..4,18 przy podlodze konczacej sie na 4,12).
# Wyrownanie ich wydluzyloby pokoj o 6 cm i przesunelo okno - to decyzja
# o wymiarze, nie o szczelnosci.

POWLOKA_CEL = {
    "Entrance end wall":     ((-0.12, 3.02), (-0.12, 0.00), (-0.15, 2.32)),
    "Window end left":       ((-0.12, 1.215), (4.12, 4.24), (-0.15, 2.32)),
    "Knee wall":             ((-0.12, 0.00), (-0.12, 4.24), (-0.15, 1.07)),
    "High wall after door":  ((2.90, 3.02), (1.04, 4.24), (-0.15, 2.32)),
    "High wall before door": ((2.90, 3.02), (-0.12, 0.12), (-0.15, 2.32)),
    "Window end right":      ((2.34, 3.02), (4.06, 4.18), (-0.15, 2.32)),
    "Under gable window":    ((1.21, 2.34), (4.06, 4.18), (-0.15, 0.72)),
}


def bryla(obiekt):
    punkty = [obiekt.matrix_world @ v.co for v in obiekt.data.vertices]
    return [(min(p[i] for p in punkty), max(p[i] for p in punkty))
            for i in range(3)]


uszczelnione = []
for nazwa, cel in POWLOKA_CEL.items():
    obiekt = bpy.data.objects.get(nazwa)
    if obiekt is None or obiekt.type != "MESH":
        continue
    przed_b = bryla(obiekt)
    material = obiekt.data.materials[0] if obiekt.data.materials else None
    plaska = any(abs(g - d) < 0.004 for d, g in przed_b)
    if plaska:
        # Plaszczyzny nie da sie rozciagnac przez dimensions - zerowy
        # wymiar mnozy sie przez cokolwiek i dalej jest zerem.
        bpy.data.objects.remove(obiekt, do_unlink=True)
        obiekt = box(nazwa,
                     tuple((d + g) / 2 for d, g in cel),
                     tuple(g - d for d, g in cel), material)
    else:
        obiekt.dimensions = tuple(g - d for d, g in cel)
        bpy.context.view_layer.update()
        nowa = bryla(obiekt)
        obiekt.location = tuple(
            obiekt.location[i] + ((cel[i][0] + cel[i][1]) / 2
                                  - (nowa[i][0] + nowa[i][1]) / 2)
            for i in range(3))
    bpy.context.view_layer.update()
    uszczelnione.append({
        "element": nazwa,
        "bylo": [[round(v, 4) for v in os_] for os_ in przed_b],
        "jest": [[round(v, 4) for v in os_] for os_ in bryla(obiekt)],
        "bylo_plaskie": plaska,
    })


# --- Sprawdzenie i zapis ------------------------------------------------
def wymiary(nazwa):
    obiekt = bpy.data.objects.get(nazwa)
    return [round(v, 4) for v in obiekt.dimensions] if obiekt else None


panel = bpy.data.objects["Headboard padded panel"]
gora_oparcia = panel.location.z + panel.dimensions.z / 2
kontrola = {
    "oparcie_grubosc_m": round(float(panel.dimensions.x), 4),
    "oparcie_wysokosc_m": round(float(panel.dimensions.z), 4),
    "oparcie_gora_nad_podloga_m": round(float(gora_oparcia), 4),
    "oparcie_gora_nad_materacem_m": round(float(gora_oparcia - MATERAC_WIERZCH), 4),
    "oparcie_lico_x_m": round(float(panel.location.x - panel.dimensions.x / 2), 4),
    "koldra": wymiary("Draped striped duvet"),
    "materac": wymiary("Mattress"),
    "baza": wymiary("Bed upholstered base"),
    "narzuta": wymiary("Mandala throw"),
}

bledy = []
if abs(kontrola["oparcie_grubosc_m"] - OPARCIE_GRUBOSC) > 0.002:
    bledy.append("grubosc oparcia nie zgadza sie z zalozeniem")
if abs(kontrola["oparcie_gora_nad_materacem_m"] - OPARCIE_NAD_MATERACEM) > 0.005:
    bledy.append("gorna krawedz oparcia nie na wysokosci z pomiaru")
if abs(kontrola["koldra"][1] - KOLDRA_SZEROKOSC) > 0.01:
    bledy.append("szerokosc koldry nie zgadza sie z zalozeniem")
if kontrola["materac"][:2] != przed.get("Mattress", [0, 0])[:2]:
    bledy.append("materac zostal ruszony, a mial zostac bez zmian")

# Powloka: zadna sciana nie moze byc plaszczyzna, a lica od strony
# wnetrza musza zostac tam, gdzie byly.
LICA_WNETRZA = {"Entrance end wall": (1, 1, 0.00), "Window end left": (1, 0, 4.12),
                "Knee wall": (0, 1, 0.00), "High wall after door": (0, 0, 2.90),
                "High wall before door": (0, 0, 2.90),
                "Window end right": (1, 0, 4.06), "Under gable window": (1, 0, 4.06)}
for wpis in uszczelnione:
    if min(g - d for d, g in wpis["jest"]) < 0.01:
        bledy.append("po uszczelnieniu {} nadal jest plaskie".format(wpis["element"]))
    os_, strona, wartosc = LICA_WNETRZA[wpis["element"]]
    if abs(wpis["jest"][os_][strona] - wartosc) > 0.001:
        bledy.append("lico wnetrza {} przesunelo sie na {}".format(
            wpis["element"], wpis["jest"][os_][strona]))
kontrola["uszczelniono_elementow"] = len(uszczelnione)

scene["bed_source"] = "gaussian splat scan work/Osowa.ply, 397047 gaussianow"
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "Room-attic-v06.blend"))
for obiekt in bpy.context.selected_objects:
    obiekt.select_set(False)
for obiekt in scene.objects:
    if obiekt.type in {"MESH", "CURVE"} and not obiekt.name.startswith("Exterior"):
        obiekt.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT / "Room-attic-v06.glb"),
                          export_format="GLB", use_selection=True,
                          export_cameras=False, export_lights=False)

raport = {
    "zrodlo_pomiaru": "work/Osowa.ply (3DGS, 397047 gaussianow, skala metryczna)",
    "co_zmieniono": {
        "oparcie": {"grubosc_z": przed.get("Headboard padded panel", [None])[0],
                    "grubosc_na": OPARCIE_GRUBOSC,
                    "gora_nad_materacem_z_m": 0.59,
                    "gora_nad_materacem_na_m": OPARCIE_NAD_MATERACEM,
                    "podstawa": "pionowa scianka 6-9 cm przy krawedzi materaca; "
                                "gestosc punktow spada 4806 -> 48 miedzy 0,40 a 0,45 m",
                    "niepewnosc_m": 0.05},
        "koldra": {"szerokosc_z_m": przed.get("Draped striped duvet", [0, 0])[1],
                   "szerokosc_na_m": KOLDRA_SZEROKOSC,
                   "podstawa": "obrys pokrycia z rantem 2,12 x 1,68 m"},
    },
    "co_potwierdzono": {
        "materac_m": przed.get("Mattress"),
        "pomiar_ze_skanu_m": [2.02, 1.589],
        "status": "zmierzone, bylo oszacowane ze zdjec",
    },
    "co_odrzucono": {
        "podniesiony_rant": "mapa wysokosci pokazywala jasna obwodke, ale to "
                            "maksimum w pikselu; mediana pasmami od brzegu jest "
                            "plaska z rozrzutem +-8 cm",
    },
    "uszczelnienie_powloki": {
        "powod": "w Unrealu swiatlo z zewnatrz wchodzilo w naroza",
        "przyczyna": "Entrance end wall i Window end left mialy zerowa grubosc, "
                     "a styki scian byly dokladne, bez zakladki",
        "zasada": "wszystko rozciagniete na zewnatrz i w dol; lica wnetrza bez zmian",
        "nie_ruszone": "bryly sciany szczytowej stoja okrakiem na krawedzi podlogi "
                       "(y 4,06..4,18 przy podlodze do 4,12) - to decyzja o wymiarze",
        "elementy": uszczelnione,
    },
    "narzuta_z_mandala": "dodana" if narzuta_dodana else "pominieta (zmiana wygladu, nie wymiaru)",
    "kontrola": kontrola,
    "bledy": bledy,
}
(OUT / "bed-review-v06.json").write_text(
    json.dumps(raport, ensure_ascii=False, indent=2), encoding="utf-8")
print("V06_KONTROLA " + json.dumps(kontrola, ensure_ascii=False))
print("V06_BLEDY " + json.dumps(bledy, ensure_ascii=False))
print("V06_DONE")
