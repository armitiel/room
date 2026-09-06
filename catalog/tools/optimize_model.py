#!/usr/bin/env python3
"""Przygotowuje model producenta do uzycia w przegladarce.

Pliki od producentow mebli sa robione pod rendering offline: pojedyncza sofa
potrafi wazyc kilkadziesiat megabajtow i miec setki tysiecy trojkatow, a cala
nasza scena domu ma ich kilkanascie tysiecy. Bez tego kroku "prawdziwy mebel"
oznacza spacer, ktory sie nie wczytuje.

Co robi: wczytuje model, redukuje siatke do zadanego budzetu trojkatow,
zmniejsza tekstury, zapisuje glTF binarny (.glb) obok wyniku.

Uruchomienie (Blender 4.x - wersja 5 nie czyta juz Collady):
    blender --background --python-exit-code 1 \
        --python catalog/tools/optimize_model.py -- \
        --in catalog/models/comforty/plik.dae \
        --out catalog/models/comforty/sofa-fin.glb \
        --triangles 20000 --texture 1024
"""

from __future__ import annotations

import argparse
import os
import sys


def parse_args(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="optimize_model.py")
    parser.add_argument("--in", dest="source", required=True)
    parser.add_argument("--out", dest="target", required=True)
    parser.add_argument("--triangles", type=int, default=20000,
                        help="Budzet trojkatow po redukcji.")
    parser.add_argument("--texture", type=int, default=1024,
                        help="Maksymalny bok tekstury w pikselach.")
    return parser.parse_args(argv)


def import_any(bpy, path):
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
    else:
        raise SystemExit("Nieobslugiwany format: {}".format(path))


def count_triangles(bpy):
    total = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.data is None:
            continue
        obj.data.calc_loop_triangles()
        total += len(obj.data.loop_triangles)
    return total


def bounds(bpy):
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
    return [round(hi[i] - lo[i], 3) for i in range(3)]


def decimate(bpy, budget):
    """Redukcja proporcjonalna: kazdy obiekt traci tyle samo procent."""
    before = count_triangles(bpy)
    if before <= budget or before == 0:
        return before, before
    ratio = max(0.02, budget / float(before))
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.data is None or len(obj.data.polygons) < 8:
            continue
        modifier = obj.modifiers.new(name="redukcja", type="DECIMATE")
        modifier.ratio = ratio
        bpy.context.view_layer.objects.active = obj
        try:
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        except RuntimeError:
            obj.modifiers.remove(modifier)
    return before, count_triangles(bpy)


def shrink_textures(bpy, max_side):
    changed = 0
    for image in bpy.data.images:
        if not image.has_data or image.size[0] == 0:
            continue
        width, height = image.size[0], image.size[1]
        longest = max(width, height)
        if longest <= max_side:
            continue
        scale = max_side / float(longest)
        image.scale(max(1, int(width * scale)), max(1, int(height * scale)))
        changed += 1
    return changed


def main():
    args = parse_args()
    try:
        import bpy
    except ImportError:
        raise SystemExit("Uruchom przez: blender --background --python ... -- --in <plik>")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    import_any(bpy, os.path.abspath(args.source))

    size = bounds(bpy)
    before, after = decimate(bpy, args.triangles)
    textures = shrink_textures(bpy, args.texture)

    target = os.path.abspath(args.target)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=target, export_format="GLB", use_selection=True,
                              export_yup=True, export_apply=True, export_extras=True)

    source_size = os.path.getsize(args.source)
    target_size = os.path.getsize(target)
    print("")
    print("Plik zrodlowy : {:>12,} B".format(source_size).replace(",", " "))
    print("Plik wynikowy : {:>12,} B  ({:.1f}% oryginalu)".format(
        target_size, 100.0 * target_size / max(source_size, 1)).replace(",", " "))
    print("Trojkaty      : {:>12,} -> {:,}".format(before, after).replace(",", " "))
    print("Tekstury zmniejszone: {}".format(textures))
    print("Gabaryt w pliku: {} m".format(size))
    print("Zapisano: {}".format(target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
