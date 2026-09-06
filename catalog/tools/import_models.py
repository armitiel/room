#!/usr/bin/env python3
"""Zamienia katalog z plikami modeli na gotowe wpisy do catalog/products.json.

Po co: producenci udostepniaja pliki w roznych formatach i prawie nigdy
w skali rzeczywistej. Recznie oznacza to otwieranie kazdego pliku, mierzenie
gabarytu i przepisywanie liczb - przy dwudziestu meblach to godzina pracy
i kilka literowek. Ten skrypt otwiera kazdy plik w Blenderze, mierzy bryle
i wypisuje wpis katalogowy z ZMIERZONYMI wymiarami pliku oraz miejscem na
wymiary rzeczywiste, ktore trzeba przepisac z karty produktu.

Wpisy powstaja jako kind=placeholder i z pusta licencja. To celowe: dopoki
nie ma pisemnej zgody producenta, wpis nie ma prawa udawac rzeczywistego
produktu, a walidator nie przepusci go do sceny zatwierdzonej.

Uruchomienie:
    blender --background --python-exit-code 1 \
        --python catalog/tools/import_models.py -- \
        --dir catalog/models/comforty --vendor "Comforty" \
        --out work/comforty-wpisy.json

Potem: uzupelnij dimensions_m wymiarami z karty produktu i wklej do
catalog/products.json.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "..", "..", "blender", "scripts"))

SUPPORTED = (".glb", ".gltf", ".fbx", ".dae", ".obj", ".stl", ".blend")


def parse_args(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="import_models.py")
    parser.add_argument("--dir", required=True, help="Katalog z plikami modeli.")
    parser.add_argument("--vendor", default="", help="Nazwa producenta (trafia do model_author).")
    parser.add_argument("--source", default="", help="Skad pochodza pliki - adres strony.")
    parser.add_argument("--out", default=None, help="Plik wynikowy JSON.")
    parser.add_argument("--prefix", default="", help="Przedrostek identyfikatorow produktow.")
    return parser.parse_args(argv)


def measure(bpy, path):
    """Gabaryt modelu w metrach, tak jak zapisano go w pliku."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    extension = os.path.splitext(path)[1].lower()
    if extension in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif extension == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif extension == ".dae":
        bpy.ops.wm.collada_import(filepath=path)
    elif extension == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif extension == ".stl":
        bpy.ops.wm.stl_import(filepath=path)
    elif extension == ".blend":
        with bpy.data.libraries.load(path, link=False) as (source, target):
            target.objects = list(source.objects)
        for obj in target.objects:
            if obj is not None:
                bpy.context.scene.collection.objects.link(obj)
    else:
        return None

    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.data is None:
            continue
        for vertex in obj.data.vertices:
            world = obj.matrix_world @ vertex.co
            for axis in range(3):
                lo[axis] = min(lo[axis], world[axis])
                hi[axis] = max(hi[axis], world[axis])
    if lo[0] == float("inf"):
        return None
    return {"x": round(hi[0] - lo[0], 3), "y": round(hi[1] - lo[1], 3), "z": round(hi[2] - lo[2], 3)}


def slug(name):
    out = []
    for char in name.lower():
        if char.isalnum():
            out.append(char)
        elif char in " _-":
            out.append("-")
    return "-".join(part for part in "".join(out).split("-") if part)


def main():
    args = parse_args()
    try:
        import bpy
    except ImportError:
        raise SystemExit(
            "Ten skrypt wymaga Blendera:\n"
            "  blender --background --python-exit-code 1 "
            "--python catalog/tools/import_models.py -- --dir <katalog>"
        )

    files = []
    for extension in SUPPORTED:
        files.extend(glob.glob(os.path.join(args.dir, "*" + extension)))
    files.sort()
    if not files:
        raise SystemExit("Nie znaleziono modeli w {} (obslugiwane: {}).".format(
            args.dir, ", ".join(SUPPORTED)))

    entries = []
    for path in files:
        name = os.path.splitext(os.path.basename(path))[0]
        measured = measure(bpy, os.path.abspath(path))
        if measured is None:
            print("POMINIETO {} - brak siatki albo format nie do odczytania".format(path))
            continue

        entries.append({
            "product_id": (args.prefix + slug(name)) if args.prefix else slug(name),
            "kind": "placeholder",
            "name": name,
            "manufacturer": None,
            "product_url": None,
            "price": None,
            "model_path": os.path.relpath(path).replace(os.sep, "/"),
            "model_author": args.vendor or None,
            "model_url": args.source or None,
            "license": "DO USTALENIA - brak potwierdzonej zgody producenta na uzycie w produkcie",
            "source": args.source or None,
            "dimensions_m": measured,
            "dimensions_source": "ZMIERZONE W PLIKU - przepisz wymiary z karty produktu i popraw te wartosci",
            "measured_in_file_m": measured,
            "materials": [],
            "note": "Wpis wygenerowany automatycznie. Przed uzyciem: uzupelnij producenta, adres "
                    "karty produktu, rzeczywiste wymiary i podstawe licencji.",
        })
        print("{:<28} {:>6.2f} x {:>6.2f} x {:>6.2f} m".format(
            name, measured["x"], measured["y"], measured["z"]))

    payload = {"schema_version": "0.1", "products": entries}
    out = args.out or os.path.join(args.dir, "wpisy-katalogowe.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print("\nZapisano {} wpisow do {}".format(len(entries), out))
    print("Wymiary powyzej sa TAKIE, JAK W PLIKU - czesto nie sa rzeczywiste.")
    print("Popraw dimensions_m wg karty produktu, potem wklej wpisy do catalog/products.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
