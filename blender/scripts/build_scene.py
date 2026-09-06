#!/usr/bin/env python3
"""Generator geometrii pomieszczenia w Blenderze.

Skrypt jest wykonawca, nie decydentem: cala arytmetyka siedzi w
roomlib.build_plan i jest pokryta testami, ktore nie potrzebuja Blendera.
Tutaj zostaje samo tworzenie siatek, boolean i zapis pliku.

Uruchomienie:
    blender --background --python-exit-code 1 \
        --python blender/scripts/build_scene.py -- \
        --scene datasets/sample/approved/scene.json

Przydatne opcje:
    --allow-unapproved   zbuduj mimo statusu innego niz approved (tylko podglad)
    --wall-thickness     grubosc scian w metrach (domyslnie 0.12)
    --out                sciezka pliku .blend (domyslnie work/scenes/<scene_id>/)
    --plan-only          zapisz sam plan JSON i zakoncz, bez budowania siatek

Kody wyjscia:
    0 - zbudowano
    1 - scena odrzucona przez walidator albo blad budowy
    2 - blad odczytu danych
"""

from __future__ import annotations

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from roomlib import build_plan, scene_io, validate  # noqa: E402
from roomlib.constants import DEFAULT_WALL_THICKNESS_M  # noqa: E402

FLOOR_THICKNESS_M = 0.15
PLACEHOLDER_PREFIX = "PLACEHOLDER_"


def parse_args(argv=None):
    """Argumenty po '--'; wszystko przed nim nalezy do Blendera.

    Bez '--' skrypt zachowuje sie jak zwykly program CLI, dzieki czemu
    --plan-only dziala takze poza Blenderem.
    """
    if argv is None:
        if "--" in sys.argv:
            argv = sys.argv[sys.argv.index("--") + 1 :]
        else:
            argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="build_scene.py")
    parser.add_argument("--scene", required=True, help="Sciezka do scene.json.")
    parser.add_argument("--catalog", default=None, help="Sciezka do catalog/products.json.")
    parser.add_argument("--out", default=None, help="Docelowy plik .blend.")
    parser.add_argument(
        "--wall-thickness",
        type=float,
        default=DEFAULT_WALL_THICKNESS_M,
        help="Grubosc scian w metrach.",
    )
    parser.add_argument(
        "--allow-unapproved",
        action="store_true",
        help="Zbuduj scene, ktora nie ma statusu approved. Wynik jest podgladem, nie dostawa.",
    )
    parser.add_argument(
        "--skip-model-files",
        action="store_true",
        help="Nie wymagaj obecnosci plikow modeli przy walidacji.",
    )
    parser.add_argument(
        "--placeholders",
        action="store_true",
        help="Zamiast brakujacych modeli wstaw oznaczone bryly zastepcze.",
    )
    parser.add_argument(
        "--plan-only", action="store_true", help="Zapisz plan JSON i zakoncz bez budowania."
    )
    return parser.parse_args(argv)


def load_inputs(args):
    scene = scene_io.load_scene(args.scene)
    root = scene_io.repo_root(os.path.abspath(args.scene))
    catalog = scene_io.load_catalog(args.catalog or scene_io.default_catalog_path(root))
    return scene, catalog, root


def gate(scene, catalog, root, args) -> validate.Report:
    """Walidacja przed budowa. Scena z bledami nie trafia do generatora."""
    report = validate.validate_scene(
        scene, catalog=catalog, root=root, check_models=not args.skip_model_files
    )
    for issue in report.sorted_issues():
        print(issue.format_line())
    if not report.ok:
        raise SystemExit(
            "Scena ma {} bledow. Popraw je albo uruchom validate_scene.py po szczegoly.".format(
                len(report.errors)
            )
        )
    if not validate.is_buildable(scene, report) and not args.allow_unapproved:
        raise SystemExit(
            "Status {!r} nie pozwala na budowe. Uzyj --allow-unapproved dla podgladu roboczego.".format(
                scene.get("status")
            )
        )
    return report


# --- Od tego miejsca kod wymaga Blendera -------------------------------------


def _bpy():
    try:
        import bpy  # noqa: F401
    except ImportError:
        raise SystemExit(
            "Ten skrypt wymaga Pythona wbudowanego w Blendera.\n"
            "Uruchom: blender --background --python-exit-code 1 "
            "--python blender/scripts/build_scene.py -- --scene <plik>"
        )
    import bpy

    return bpy


def clear_scene(bpy) -> None:
    """Czysty plik startowy. Generator ma byc powtarzalny, nie przyrostowy."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def ensure_collection(bpy, name, parent=None):
    collection = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(collection)
    return collection


def make_prism(bpy, name, base_xy, z_bottom, z_top, collection):
    """Bryla o pionowych scianach na podstawie wielokata base_xy."""
    import bmesh

    count = len(base_xy)
    vertices = [(float(x), float(y), z_bottom) for x, y in base_xy]
    vertices += [(float(x), float(y), z_top) for x, y in base_xy]

    faces = [tuple(range(count - 1, -1, -1)), tuple(range(count, 2 * count))]
    for index in range(count):
        nxt = (index + 1) % count
        faces.append((index, nxt, nxt + count, index + count))

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=False)

    # Normalne liczymy maszynowo - kolejnosc wierzcholkow w rzucie
    # bywa rozna i nie chcemy jej zgadywac.
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def make_box(bpy, name, center, size, rotation_deg, collection):
    import math

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0], size[1], size[2])
    obj.rotation_euler = (0.0, 0.0, math.radians(rotation_deg))
    for existing in list(obj.users_collection):
        existing.objects.unlink(obj)
    collection.objects.link(obj)
    return obj


def apply_boolean(bpy, target, cutter):
    """Odejmuje cutter od target i stosuje modyfikator na stale."""
    modifier = target.modifiers.new(name="cut_" + cutter.name, type="BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.object = cutter
    if hasattr(modifier, "solver"):
        modifier.solver = "EXACT"

    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def build_room(bpy, room_plan, parent_collection, report_lines):
    room_id = room_plan["room_id"] or "room"
    room_collection = ensure_collection(bpy, "room_" + room_id, parent_collection)

    floor = make_prism(
        bpy,
        "floor_" + room_id,
        room_plan["polygon"],
        -FLOOR_THICKNESS_M,
        0.0,
        room_collection,
    )
    floor["room_id"] = room_id
    floor["role"] = "floor"

    cutters_collection = ensure_collection(bpy, "cutters_" + room_id, room_collection)
    cutters = {}
    for index, cut in enumerate(room_plan["openings"]):
        cutter = make_box(
            bpy,
            "cut_{}_{}_{}".format(room_id, cut["kind"], index),
            cut["center_m"],
            cut["size_m"],
            cut["rotation_deg"],
            cutters_collection,
        )
        cutters.setdefault(cut["wall_index"], []).append(cutter)

    for wall_plan in room_plan["walls"]:
        wall = make_prism(
            bpy,
            "wall_{}_{}".format(room_id, wall_plan["source_wall_index"]),
            wall_plan["base"],
            0.0,
            wall_plan["height_m"],
            room_collection,
        )
        wall["room_id"] = room_id
        wall["wall_index"] = wall_plan["source_wall_index"]
        wall["role"] = "wall"

        for cutter in cutters.get(wall_plan["index"], []):
            apply_boolean(bpy, wall, cutter)
            report_lines.append(
                "Wyciety otwor {} w scianie {} pomieszczenia {}.".format(
                    cutter.name, wall_plan["source_wall_index"], room_id
                )
            )

    # Bryly tnace nie sa czescia dostawy - zostaja ukryte na wypadek kontroli.
    for cutter_list in cutters.values():
        for cutter in cutter_list:
            cutter.hide_set(True)
            cutter.hide_render = True

    return room_collection


def import_model(bpy, path):
    """Import pliku modelu. Zwraca liste utworzonych obiektow."""
    before = set(bpy.data.objects)
    extension = os.path.splitext(path)[1].lower()

    if extension in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif extension == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif extension == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=path)
        else:
            bpy.ops.import_scene.obj(filepath=path)
    elif extension == ".blend":
        with bpy.data.libraries.load(path, link=False) as (source, target):
            target.objects = list(source.objects)
        for obj in target.objects:
            if obj is not None:
                bpy.context.scene.collection.objects.link(obj)
    else:
        raise SystemExit("Nieobslugiwany format modelu: {}".format(path))

    return [obj for obj in bpy.data.objects if obj not in before]


def build_furniture(bpy, plan, root, parent_collection, args, report_lines):
    import math

    collection = ensure_collection(bpy, "furniture", parent_collection)
    for item in plan["furniture"]:
        name = item["id"] or item["product_id"] or "mebel"
        model_path = item["model_path"]
        absolute = (
            model_path
            if model_path and os.path.isabs(model_path)
            else (os.path.join(root, model_path) if model_path else None)
        )

        # position_m opisuje SPOD mebla na podlodze. Zaimportowany model ma
        # zwykle wlasny punkt odniesienia u podstawy, a bryla zastepcza ma
        # srodek w polowie wysokosci - stad rozne podniesienie.
        lift = 0.0

        if absolute and os.path.isfile(absolute):
            created = import_model(bpy, absolute)
            if not created:
                report_lines.append("Plik {} nie zawieral zadnego obiektu.".format(absolute))
                continue
            empty = bpy.data.objects.new("anchor_" + name, None)
            collection.objects.link(empty)
            for obj in created:
                for existing in list(obj.users_collection):
                    existing.objects.unlink(obj)
                collection.objects.link(obj)
                if obj.parent is None:
                    obj.parent = empty
            holder = empty
        elif args.placeholders:
            dimensions = item["dimensions_m"] or {}
            size = (
                float(dimensions.get("x", 0.5)),
                float(dimensions.get("y", 0.5)),
                float(dimensions.get("z", 0.5)),
            )
            holder = make_box(bpy, PLACEHOLDER_PREFIX + name, (0.0, 0.0, 0.0), size, 0.0, collection)
            lift = size[2] / 2.0
            report_lines.append(
                "Brak modelu dla {!r} - wstawiono bryle zastepcza. Nie pokazuj tego klientowi.".format(
                    item["product_id"]
                )
            )
        else:
            report_lines.append(
                "Pominieto {!r}: brak pliku modelu. Uzyj --placeholders dla podgladu.".format(
                    item["product_id"]
                )
            )
            continue

        holder.location = (
            item["location_m"][0],
            item["location_m"][1],
            item["location_m"][2] + lift,
        )
        holder.rotation_euler = (0.0, 0.0, math.radians(item["rotation_deg"]))
        holder["furniture_id"] = item["id"] or ""
        holder["product_id"] = item["product_id"] or ""
        holder["room_id"] = item["room_id"] or ""

    return collection


def main() -> int:
    args = parse_args()

    try:
        scene, catalog, root = load_inputs(args)
    except scene_io.SceneIOError as exc:
        print("Nie mozna wczytac danych: {}".format(exc), file=sys.stderr)
        return 2

    gate(scene, catalog, root, args)

    plan = build_plan.plan_scene(scene, catalog, args.wall_thickness)
    scene_id = plan["scene_id"] or "scena"
    output_dir = scene_io.work_dir(scene_id, root)
    scene_io.write_json(os.path.join(output_dir, "plan.json"), plan)
    print("Plan zapisany: {}".format(os.path.join(output_dir, "plan.json")))
    print(
        "Do zbudowania: {rooms} pomieszczen, {walls} scian, {openings} otworow, "
        "{furniture} mebli, {floor_area_m2} m2 podlogi.".format(**plan["totals"])
    )

    if args.plan_only:
        return 0

    bpy = _bpy()
    clear_scene(bpy)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0

    report_lines = []
    root_collection = ensure_collection(bpy, "scene_" + scene_id)
    rooms_collection = ensure_collection(bpy, "rooms", root_collection)

    for room_plan in plan["rooms"]:
        build_room(bpy, room_plan, rooms_collection, report_lines)

    build_furniture(bpy, plan, root, root_collection, args, report_lines)

    blend_path = args.out or os.path.join(output_dir, "{}.blend".format(scene_id))
    os.makedirs(os.path.dirname(os.path.abspath(blend_path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    scene_io.write_json(
        os.path.join(output_dir, "build_report.json"),
        {
            "scene_id": scene_id,
            "status": scene.get("status"),
            "blend_path": blend_path,
            "wall_thickness_m": args.wall_thickness,
            "totals": plan["totals"],
            "notes": report_lines,
        },
    )

    print("Zapisano: {}".format(blend_path))
    for line in report_lines:
        print("  - {}".format(line))
    return 0


if __name__ == "__main__":
    sys.exit(main())
