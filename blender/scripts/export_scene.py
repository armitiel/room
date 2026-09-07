#!/usr/bin/env python3
"""Eksport sceny z Blendera do formatu przyjmowanego przez Unreal.

Skrypt niczego nie zaklada o transferze. Zapisuje obok pliku wynikowego
raport z dokladnie tymi ustawieniami, ktorych uzyl: jednostki, skala, osie
i lista wyeksportowanych obiektow. Ten raport jest punktem odniesienia przy
pierwszym imporcie w Unreal - jesli cos przyjdzie obrocone albo w zlej skali,
poprawiamy jedna wartosc, zamiast zgadywac.

Uruchomienie na gotowym pliku:
    blender --background work/scenes/<id>/<id>.blend \
        --python blender/scripts/export_scene.py -- --format fbx

Uruchomienie od scene.json (buduje i eksportuje za jednym razem):
    blender --background --python-exit-code 1 \
        --python blender/scripts/build_scene.py -- --scene <plik>
    blender --background work/scenes/<id>/<id>.blend \
        --python blender/scripts/export_scene.py -- --format gltf

Kody wyjscia:
    0 - wyeksportowano
    1 - blad eksportu
"""

from __future__ import annotations

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from roomlib import scene_io  # noqa: E402

# Unreal pracuje w centymetrach, Blender w metrach.
METRES_TO_UNREAL_UNITS = 100.0

# Konwencja osi przy eksporcie FBX do Unreal. Traktuj to jako wartosc
# startowa do sprawdzenia przy pierwszym imporcie, nie jako pewnik.
FBX_AXIS_FORWARD = "-Z"
FBX_AXIS_UP = "Y"


def parse_args(argv=None):
    if argv is None:
        if "--" in sys.argv:
            argv = sys.argv[sys.argv.index("--") + 1 :]
        else:
            argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="export_scene.py")
    parser.add_argument(
        "--format",
        choices=("fbx", "gltf", "glb"),
        default="fbx",
        help="Format wyjsciowy. FBX do Unreal, glTF do podgladu w przegladarce.",
    )
    parser.add_argument("--out", default=None, help="Sciezka pliku wynikowego.")
    parser.add_argument(
        "--scene-id",
        default=None,
        help="Identyfikator sceny; domyslnie brany z nazwy otwartego pliku .blend.",
    )
    parser.add_argument(
        "--units",
        choices=("m", "cm"),
        default="cm",
        help="Jednostki pliku wynikowego. 'cm' odpowiada domyslnym jednostkom Unreal.",
    )
    parser.add_argument(
        "--include-placeholders",
        action="store_true",
        help="Nie pomijaj bryl zastepczych wstawionych zamiast brakujacych modeli.",
    )
    return parser.parse_args(argv)


def _bpy():
    try:
        import bpy  # noqa: F401
    except ImportError:
        raise SystemExit(
            "Ten skrypt wymaga Pythona wbudowanego w Blendera.\n"
            "Uruchom: blender --background <plik.blend> "
            "--python blender/scripts/export_scene.py -- --format fbx"
        )
    import bpy

    return bpy


def scale_factor(units: str) -> float:
    return METRES_TO_UNREAL_UNITS if units == "cm" else 1.0


CUTTER_PREFIX = "cut_"
PLACEHOLDER_PREFIX = "PLACEHOLDER_"


def partition_objects(bpy, include_placeholders):
    """Dzieli siatki sceny na eksportowane i swiadomie pominiete.

    Bryly tnace sluza wylacznie do wyciecia otworow i nie sa czescia
    dostawy. Bryly zastepcze zastepuja brakujace modele - wypuszczenie ich
    do Unreal wygladaloby jak gotowa scena, wiec domyslnie zostaja w domu.
    """
    exported, skipped = [], []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if obj.name.startswith(CUTTER_PREFIX):
            skipped.append(obj.name)
            continue
        if obj.name.startswith(PLACEHOLDER_PREFIX) and not include_placeholders:
            skipped.append(obj.name)
            continue
        exported.append(obj)
    return exported, sorted(skipped)


def export_fbx(bpy, path, args):
    # use_selection=True jest obowiazkowe: to jedyny sposob, w ktory
    # zaznaczenie zbudowane powyzej faktycznie ogranicza zawartosc pliku.
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        global_scale=scale_factor(args.units),
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_NONE",
        axis_forward=FBX_AXIS_FORWARD,
        axis_up=FBX_AXIS_UP,
        object_types={"MESH", "EMPTY"},
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        bake_space_transform=False,
    )


def export_gltf(bpy, path, args):
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB" if args.format == "glb" else "GLTF_SEPARATE",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_extras=True,
    )


def main() -> int:
    args = parse_args()
    bpy = _bpy()

    blend_path = bpy.data.filepath
    scene_id = args.scene_id or (
        os.path.splitext(os.path.basename(blend_path))[0] if blend_path else "scena"
    )

    try:
        root = scene_io.repo_root(blend_path or SCRIPT_DIR)
    except scene_io.SceneIOError:
        root = None

    if args.out:
        out_path = args.out
    else:
        directory = scene_io.work_dir(scene_id, root) if root else os.getcwd()
        extension = {"fbx": ".fbx", "gltf": ".gltf", "glb": ".glb"}[args.format]
        out_path = os.path.join(directory, scene_id + extension)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    exported, skipped = partition_objects(bpy, args.include_placeholders)
    if not exported:
        print("Scena nie zawiera zadnej siatki do eksportu.", file=sys.stderr)
        return 1

    bpy.ops.object.select_all(action="DESELECT")
    for obj in exported:
        obj.select_set(True)
        # Product identifiers live on the furniture anchor, not on its meshes.
        # Keep that hierarchy in glTF so the viewer can style and collide with
        # a whole piece of furniture instead of guessing from mesh names.
        parent = obj.parent
        while parent is not None:
            if parent.type == "EMPTY":
                parent.select_set(True)
            parent = parent.parent
    bpy.context.view_layer.objects.active = exported[0]

    if args.format == "fbx":
        export_fbx(bpy, out_path, args)
    else:
        export_gltf(bpy, out_path, args)

    # glTF z definicji zapisuje metry - nie udajemy, ze zastosowalismy skale.
    is_fbx = args.format == "fbx"
    effective_units = args.units if is_fbx else "m"
    effective_scale = scale_factor(args.units) if is_fbx else 1.0
    if not is_fbx and args.units != "m":
        print(
            "Uwaga: glTF zapisuje metry. Zignorowano --units {}; "
            "przeskaluj przy imporcie po stronie silnika.".format(args.units)
        )

    report = {
        "scene_id": scene_id,
        "source_blend": blend_path,
        "output": out_path,
        "format": args.format,
        "units": effective_units,
        "scale_applied": effective_scale,
        "axis_forward": FBX_AXIS_FORWARD if is_fbx else "gltf_y_up",
        "axis_up": FBX_AXIS_UP if is_fbx else "gltf_y_up",
        "object_count": len(exported),
        "objects": sorted(obj.name for obj in exported),
        "skipped_objects": skipped,
        "verify_on_first_import": [
            "Zmierz w Unreal jedna sciane i porownaj z rzutem.",
            "Sprawdz kierunek polnocy i czy pomieszczenie nie jest odbite.",
            "Sprawdz, czy normalne scian patrza do wnetrza pomieszczenia.",
            "Sprawdz, czy otwory maja swiatlo zgodne z scene.json.",
        ],
    }

    report_path = os.path.splitext(out_path)[0] + "_export_report.json"
    scene_io.write_json(report_path, report)

    print("Wyeksportowano {} obiektow do {}".format(len(exported), out_path))
    print("Skala: x{} ({}), osie: forward={}, up={}".format(
        report["scale_applied"], effective_units, report["axis_forward"], report["axis_up"]
    ))
    if skipped:
        print("Pominieto (bryly tnace i zastepcze): {}".format(", ".join(skipped)))
    print("Raport eksportu: {}".format(report_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
