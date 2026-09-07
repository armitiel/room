#!/usr/bin/env python3
"""Eksport sceny do Unreala razem z manifestem, ktory opisuje kazda siatke.

Po co osobny skrypt zamiast export_scene.py: Unreal nazywa zasoby po nazwach
wezlow FBX, a nazwy z Blendera nie sa unikalne po oczyszczeniu (chair(Clone),
chair(Clone).001, polskie znaki, kropki). Gdyby importer po stronie silnika
zgadywal role z takich nazw, czesc mebli nadpisalaby sie nawzajem i scena
przyszlaby niepelna, a nikt by tego nie zauwazyl.

Dlatego kazdy obiekt dostaje tu krotki, unikalny identyfikator ASCII, a
manifest niesie prawde o nim: rola, pomieszczenie, mebel, produkt i wymiary
bryly w metrach. Unreal nie zgaduje niczego - czyta manifest.

Uruchomienie:
    blender --background work/scenes/showcase/main.blend \
        --python-exit-code 1 --python blender/scripts/export_unreal.py -- \
        --fbx work/unreal/room.fbx --manifest work/unreal/room-manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import export_scene  # noqa: E402

METRES_TO_UNREAL_UNITS = 100.0
# "skirting" jest tu razem z podloga i sciana, bo listwa to powierzchnia
# budowlana - ma wlasne gniazdo materialowe w kontrakcie wariantow, wiec musi
# dac sie przelaczyc razem z reszta wykonczenia.
SURFACE_ROLES = ("floor", "wall", "ceiling", "skirting", "frame_window",
                 "frame_door", "glass", "leaf")


def parse_args(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="export_unreal.py")
    parser.add_argument("--fbx", required=True, help="Sciezka pliku FBX.")
    parser.add_argument("--manifest", required=True, help="Sciezka manifestu JSON.")
    parser.add_argument("--scene-id", default=None)
    parser.add_argument("--roles", default=None,
                        help="Mapa nazwa obiektu -> rola dla scen bez "
                             "wlasciwosci z build_scene.py.")
    parser.add_argument("--no-bevel", action="store_true",
                        help="Nie dokladaj fazki na krawedziach przy eksporcie.")
    parser.add_argument("--include-placeholders", action="store_true",
                        help="Nie pomijaj bryl zastepczych zamiast brakujacych modeli.")
    return parser.parse_args(argv)


def world_bounds_m(obj):
    """Skrajne punkty bryly obiektu w ukladzie sceny, w metrach.

    Liczymy recznie z macierzy, zeby nie zalezec od mathutils poza Blenderem.
    """
    matrix = obj.matrix_world
    xs, ys, zs = [], [], []
    for corner in obj.bound_box:
        xs.append(matrix[0][0] * corner[0] + matrix[0][1] * corner[1]
                  + matrix[0][2] * corner[2] + matrix[0][3])
        ys.append(matrix[1][0] * corner[0] + matrix[1][1] * corner[1]
                  + matrix[1][2] * corner[2] + matrix[1][3])
        zs.append(matrix[2][0] * corner[0] + matrix[2][1] * corner[1]
                  + matrix[2][2] * corner[2] + matrix[2][3])
    return [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]


def anchor_of(obj):
    """Najblizszy rodzic typu EMPTY, czyli kotwica mebla."""
    parent = obj.parent
    while parent is not None:
        if parent.type == "EMPTY":
            return parent
        parent = parent.parent
    return None


def prop(obj, key, default=""):
    try:
        value = obj[key]
    except KeyError:
        return default
    return value if value is not None else default


def load_roles(path):
    """Mapa nazwa obiektu -> rola, dla scen bez wlasciwosci z build_scene.py.

    Rekonstrukcja pokoju ze zdjec ma sensowne nazwy ("Knee wall", "Floor
    slab"), ale zadnych wlasciwosci. Bez tej mapy wszystko wyszloby jako
    mebel i warianty nie mialyby czego zmieniac.
    """
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    rules = [(str(rule["prefix"]), str(rule["role"]))
             for rule in data.get("rules", [])]
    # Wygrywa najdluzszy pasujacy prefiks, wiec kolejnosc regul w pliku nie ma
    # znaczenia: "High wall skirting" nie wpadnie do reguly "High wall".
    rules.sort(key=lambda item: len(item[0]), reverse=True)
    return {"rules": rules,
            "default_role": str(data.get("default_role", "furniture")),
            "room_id": str(data.get("room_id", "")),
            "path": os.path.abspath(path)}


def role_from_map(name, roles):
    for prefix, role in roles["rules"]:
        if name.startswith(prefix):
            return role
    return roles["default_role"]


def describe(obj, index, roles=None):
    """Opis jednej siatki: rola i przynaleznosc, wprost z danych obiektu.

    Rola i pomieszczenie sa zapisane jako wlasciwosci obiektu przez
    build_scene.py. Scena, ktora przez build_scene.py nie przeszla, nie ma ich
    wcale - wtedy role daje mapa nazw z --roles. Nazwa jest ostatnim zapasem.
    """
    role = str(prop(obj, "role", ""))
    room_id = str(prop(obj, "room_id", ""))
    anchor = anchor_of(obj)

    if not role and roles is not None:
        role = role_from_map(obj.name, roles)
    if not room_id and roles is not None:
        room_id = roles["room_id"]
    if not role and anchor is not None:
        role = "furniture"
    if not role:
        head = obj.name.split("_")[0]
        role = head if head in SURFACE_ROLES else "furniture"
    if not room_id and anchor is not None:
        room_id = str(prop(anchor, "room_id", ""))

    kind = "surface" if role in SURFACE_ROLES else "furniture"
    prefix = "S" if kind == "surface" else "F"
    low, high = world_bounds_m(obj)
    location, quaternion, scale = obj.matrix_world.decompose()
    return {
        "id": "{}{:04d}".format(prefix, index),
        "kind": kind,
        "role": role,
        "room_id": room_id,
        # Transformacja w ukladzie Blendera. Przeliczenie na uklad Unreala
        # robi importer po stronie silnika, w jednym miejscu i z kontrola.
        "location_m": [round(v, 6) for v in location],
        "quaternion_wxyz": [round(quaternion.w, 8), round(quaternion.x, 8),
                            round(quaternion.y, 8), round(quaternion.z, 8)],
        "scale": [round(v, 6) for v in scale],
        "blender_name": obj.name,
        "anchor_name": anchor.name if anchor is not None else "",
        "product_id": str(prop(anchor, "product_id", "")) if anchor is not None else "",
        "bounds_min_m": [round(v, 4) for v in low],
        "bounds_max_m": [round(v, 4) for v in high],
        # Bryla w ukladzie samej siatki. Pozwala sprawdzic osobno, czy silnik
        # dobrze wczytal geometrie, a osobno czy dobrze ja ustawilismy.
        "local_min_m": [round(min(c[a] for c in obj.bound_box), 4) for a in range(3)],
        "local_max_m": [round(max(c[a] for c in obj.bound_box), 4) for a in range(3)],
        "triangles": len(obj.data.loop_triangles) if obj.data.loop_triangles else None,
    }


BEVEL_WIDTH_M = 0.0025


def add_bevels(objects, width_m=BEVEL_WIDTH_M):
    """Dokladamy mala fazke na kazda bryle, tylko na czas eksportu.

    Prawdziwy przedmiot nie ma matematycznie ostrej krawedzi - ma na niej
    ulamek milimetra zaokraglenia, ktory lapie swiatlo jasna kreska. Bez tego
    kazde pudelko czyta sie jak karton, niezaleznie od tego, jak dobrze jest
    oswietlone. 2,5 mm to tyle, ile widac, a nie tyle, zeby zmienic wymiar.

    "Clamp overlap" pilnuje drobiazgow: srubka ma 6 mm, wiec dostanie fazke
    mniejsza, zamiast zwinac sie w kule. Modyfikatory zdejmujemy po eksporcie,
    zeby plik uzytkownika zostal taki, jaki byl.
    """
    dodane = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        modifier = obj.modifiers.new(name="ROOM_FAZKA", type="BEVEL")
        modifier.width = width_m
        modifier.segments = 2
        modifier.limit_method = "ANGLE"
        modifier.angle_limit = math.radians(30.0)
        modifier.use_clamp_overlap = True
        dodane.append((obj, modifier))
    return dodane


def remove_bevels(dodane):
    for obj, modifier in dodane:
        try:
            obj.modifiers.remove(modifier)
        except Exception:  # noqa: BLE001 - obiekt mogl juz zniknac
            pass


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    import bpy

    exported, skipped = export_scene.partition_objects(bpy, args.include_placeholders)
    if not exported:
        print("Scena nie zawiera zadnej siatki do eksportu.", file=sys.stderr)
        return 1

    # Trojkaty licza sie dopiero po tej operacji; bez niej loop_triangles jest puste.
    for obj in exported:
        obj.data.calc_loop_triangles()

    exported.sort(key=lambda obj: obj.name)
    roles = load_roles(args.roles) if args.roles else None
    entries = [describe(obj, index, roles) for index, obj in enumerate(exported)]

    # Kotwice mebli tez trafiaja do FBX jako puste wezly - ich nazwy moga
    # zderzyc sie po oczyszczeniu tak samo jak nazwy siatek.
    anchors = []
    for obj in exported:
        anchor = anchor_of(obj)
        if anchor is not None and anchor not in anchors:
            anchors.append(anchor)
    anchors.sort(key=lambda obj: obj.name)

    # Unreal nazywa zasoby po nazwie GEOMETRII w FBX, a Blender bierze ja z
    # obj.data, nie z obj.name. Bez tego 246 obiektow dalo 241 zasobow o
    # nazwach w rodzaju "Null" i "NONE_005" - piec siatek przepadlo po cichu.
    original = {}
    original_data = {}
    for entry, obj in zip(entries, exported):
        original[obj] = obj.name
        obj.name = entry["id"]
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        original_data[obj] = obj.data.name
        obj.data.name = entry["id"]
        if obj.name != entry["id"] or obj.data.name != entry["id"]:
            raise SystemExit(
                "Nazwa {} juz zajeta w scenie - eksport przerwany, zeby nie "
                "wypuscic pliku z niejednoznacznymi nazwami".format(entry["id"]))
    anchor_map = []
    for index, obj in enumerate(anchors):
        original[obj] = obj.name
        anchor_map.append({
            "id": "A{:04d}".format(index),
            "blender_name": obj.name,
            "product_id": str(prop(obj, "product_id", "")),
            "room_id": str(prop(obj, "room_id", "")),
        })
        obj.name = anchor_map[-1]["id"]

    fazki = [] if args.no_bevel else add_bevels(exported)
    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.fbx)), exist_ok=True)
        bpy.ops.object.select_all(action="DESELECT")
        for obj in exported:
            obj.select_set(True)
        for obj in anchors:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = exported[0]
        bpy.ops.export_scene.fbx(
            filepath=args.fbx,
            use_selection=True,
            global_scale=METRES_TO_UNREAL_UNITS,
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_NONE",
            axis_forward=export_scene.FBX_AXIS_FORWARD,
            axis_up=export_scene.FBX_AXIS_UP,
            object_types={"MESH", "EMPTY"},
            use_mesh_modifiers=True,
            mesh_smooth_type="FACE",
            bake_space_transform=False,
            # Obrazki siedza spakowane w blendzie. Bez tych dwoch linii FBX
            # wychodzi bez ani jednej tekstury i w Unrealu wszystko jest
            # plaskim kolorem - splot tapicerki, sloj drewna i zdjecie za
            # oknem po prostu nie istnieja.
            path_mode="COPY",
            embed_textures=True,
        )
    finally:
        remove_bevels(fazki)
        for obj, name in original.items():
            obj.name = name
        for obj, name in original_data.items():
            obj.data.name = name

    scene_id = args.scene_id or (
        os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        if bpy.data.filepath else "scena"
    )
    all_low = [min(e["bounds_min_m"][axis] for e in entries) for axis in range(3)]
    all_high = [max(e["bounds_max_m"][axis] for e in entries) for axis in range(3)]

    manifest = {
        "manifest_version": 1,
        "scene_id": scene_id,
        "source_blend": bpy.data.filepath,
        "fbx": os.path.abspath(args.fbx),
        "fbx_sha256": sha256(args.fbx),
        "units": "cm",
        "scale_applied": METRES_TO_UNREAL_UNITS,
        "axis_forward": export_scene.FBX_AXIS_FORWARD,
        "axis_up": export_scene.FBX_AXIS_UP,
        "bounds_min_m": [round(v, 4) for v in all_low],
        "bounds_max_m": [round(v, 4) for v in all_high],
        "size_m": [round(all_high[a] - all_low[a], 4) for a in range(3)],
        "mesh_count": len(entries),
        "role_map": roles["path"] if roles else "",
        "meshes": entries,
        "anchors": anchor_map,
        "skipped_objects": skipped,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.manifest)), exist_ok=True)
    with open(args.manifest, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=1)

    licznik_rol = {}
    for entry in entries:
        licznik_rol[entry["role"]] = licznik_rol.get(entry["role"], 0) + 1
    print("FBX: {} ({} siatek, {} kotwic)".format(args.fbx, len(entries), len(anchor_map)))
    print("Bryla sceny [m]: {}".format(manifest["size_m"]))
    print("Role: {}".format(", ".join("{}={}".format(k, licznik_rol[k])
                                      for k in sorted(licznik_rol))))
    if roles:
        print("Mapa rol: {}".format(roles["path"]))
    print("Manifest: {}".format(args.manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
