#!/usr/bin/env python3
"""Sklada web/index.html w jeden plik dzialajacy bez serwera i bez sieci.

Po co: przegladarka blokuje fetch() oraz import modulow spod adresow file://,
wiec plik do wyslania mailem albo pokazania na spotkaniu bez internetu musi
miec wszystko w srodku. Skrypt wstrzykuje model, scene i biblioteke three.js
jako dane osadzone. Zadnej innej roznicy miedzy wersjami nie ma, wiec nie moga
sie rozjechac.

Uzycie:
    python3 web/tools/build_standalone.py
    python3 web/tools/build_standalone.py --out web/pokaz.html
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "..", "..", "blender", "scripts"))

from roomlib import scene_io  # noqa: E402

IMPORTMAP_RE = re.compile(r'<script type="importmap">.*?</script>', re.DOTALL)
WARN_BYTES = 12 * 1024 * 1024

# Modul wczytany z data: URI traci kontekst katalogu, wiec sciezki wzgledne
# w srodku bibliotek trzeba zamienic na nazwy z mapy importow.
REWRITES = {
    "../utils/BufferGeometryUtils.js": "three/addons/utils/BufferGeometryUtils.js",
}

VENDOR_MODULES = [
    ("three", "three/three.module.min.js"),
    ("three/addons/utils/BufferGeometryUtils.js", "three/addons/utils/BufferGeometryUtils.js"),
    ("three/addons/loaders/GLTFLoader.js", "three/addons/loaders/GLTFLoader.js"),
    ("three/addons/controls/OrbitControls.js", "three/addons/controls/OrbitControls.js"),
    ("three/addons/environments/RoomEnvironment.js", "three/addons/environments/RoomEnvironment.js"),
]


def data_uri(text, mime="text/javascript;charset=utf-8"):
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return "data:{};base64,{}".format(mime, encoded)


def read_module(vendor_dir, relative):
    path = os.path.join(vendor_dir, *relative.split("/"))
    if not os.path.isfile(path):
        raise SystemExit("Brak pliku biblioteki: {}".format(path))
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    for old, new in REWRITES.items():
        source = source.replace("'{}'".format(old), "'{}'".format(new))
        source = source.replace('"{}"'.format(old), '"{}"'.format(new))
    return source


def build(template_path, model_path, scene_path, vendor_dir, output_path):
    with open(template_path, "r", encoding="utf-8") as handle:
        html = handle.read()
    with open(model_path, "rb") as handle:
        model_bytes = handle.read()
    with open(scene_path, "r", encoding="utf-8") as handle:
        scene = json.load(handle)

    imports = {}
    for specifier, relative in VENDOR_MODULES:
        imports[specifier] = data_uri(read_module(vendor_dir, relative))

    if not IMPORTMAP_RE.search(html):
        raise SystemExit("Nie znaleziono mapy importow w szablonie - sprawdz web/index.html.")

    payload = (
        "<script>\n"
        'window.ROOM_MODEL_URL = "data:model/gltf-binary;base64,{model}";\n'
        "window.ROOM_SCENE = {scene};\n"
        "</script>\n"
        '<script type="importmap">\n{imports}\n</script>'
    ).format(
        model=base64.b64encode(model_bytes).decode("ascii"),
        scene=json.dumps(scene, ensure_ascii=False),
        imports=json.dumps({"imports": imports}, indent=2),
    )

    html = IMPORTMAP_RE.sub(lambda _: payload, html, count=1)

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(html)

    return len(html.encode("utf-8")), len(model_bytes)


def main(argv=None):
    root = scene_io.repo_root(SCRIPT_DIR)
    parser = argparse.ArgumentParser(prog="build_standalone.py")
    parser.add_argument("--template", default=os.path.join(root, "web", "index.html"))
    parser.add_argument("--model", default=os.path.join(root, "web", "assets", "room.glb"))
    parser.add_argument("--scene", default=os.path.join(root, "web", "scene.json"))
    parser.add_argument("--vendor", default=os.path.join(root, "web", "vendor"))
    parser.add_argument("--out", default=os.path.join(root, "web", "standalone.html"))
    args = parser.parse_args(argv)

    for path in (args.template, args.model, args.scene):
        if not os.path.isfile(path):
            raise SystemExit("Brak pliku: {}".format(path))

    total, model_size = build(args.template, args.model, args.scene, args.vendor, args.out)
    print(
        "Zapisano {} ({:.1f} kB; model {:.1f} kB przed kodowaniem).".format(
            args.out, total / 1024, model_size / 1024
        )
    )
    if total > WARN_BYTES:
        print(
            "Uwaga: plik przekracza {:.0f} MB - do wysylki mailem lepiej nadaje sie "
            "wersja z GitHub Pages.".format(WARN_BYTES / 1024 / 1024)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
