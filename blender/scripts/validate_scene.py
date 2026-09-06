#!/usr/bin/env python3
"""Walidator scene.json.

Nie wymaga Blendera - to zwykly skrypt Pythona, wiec mozna go wpiac
w backend albo w CI zanim ktokolwiek uruchomi silnik graficzny.

Uzycie:
    python3 blender/scripts/validate_scene.py --scene datasets/sample/approved/scene.json
    python3 blender/scripts/validate_scene.py --scene <plik> --json --out work/report.json
    python3 blender/scripts/validate_scene.py --scene <plik> --require-buildable

Kody wyjscia:
    0 - brak bledow
    1 - scena zawiera bledy (albo --require-buildable nie jest spelnione)
    2 - nie udalo sie wczytac pliku
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from roomlib import scene_io, validate  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_scene.py",
        description="Sprawdza scene.json wzgledem kontraktu z docs/architecture.md.",
    )
    parser.add_argument("--scene", required=True, help="Sciezka do pliku scene.json.")
    parser.add_argument(
        "--catalog",
        default=None,
        help="Sciezka do catalog/products.json. Domyslnie katalog z repozytorium.",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Wypisz raport jako JSON zamiast tekstu."
    )
    parser.add_argument("--out", default=None, help="Zapisz raport JSON do pliku.")
    parser.add_argument(
        "--skip-model-files",
        action="store_true",
        help="Nie sprawdzaj obecnosci plikow modeli na dysku (przydatne w CI bez zasobow).",
    )
    parser.add_argument(
        "--require-buildable",
        action="store_true",
        help="Zakoncz bledem, jesli scena nie ma statusu approved.",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Wypisz wylacznie podsumowanie i bledy."
    )
    return parser


def print_text_report(report: validate.Report, scene_path: str, quiet: bool) -> None:
    print("Scena: {}".format(scene_path))
    issues = report.sorted_issues()
    if quiet:
        issues = [i for i in issues if i.severity == validate.ERROR]

    if not issues:
        print("Brak zastrzezen.")
    else:
        print("")
        for issue in issues:
            print(issue.format_line())
            print("")

    counts = report.as_dict()["counts"]
    print(
        "Podsumowanie: {} bledow, {} ostrzezen, {} informacji.".format(
            counts["error"], counts["warning"], counts["info"]
        )
    )


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        scene = scene_io.load_scene(args.scene)
    except scene_io.SceneIOError as exc:
        print("Nie mozna wczytac sceny: {}".format(exc), file=sys.stderr)
        return 2

    try:
        root = scene_io.repo_root(os.path.abspath(args.scene))
    except scene_io.SceneIOError:
        root = None

    try:
        catalog = scene_io.load_catalog(args.catalog or (scene_io.default_catalog_path(root) if root else None))
    except scene_io.SceneIOError as exc:
        print("Nie mozna wczytac katalogu: {}".format(exc), file=sys.stderr)
        return 2

    report = validate.validate_scene(
        scene, catalog=catalog, root=root, check_models=not args.skip_model_files
    )

    duplicates = []
    try:
        duplicates = scene_io.duplicate_product_ids(
            args.catalog or (scene_io.default_catalog_path(root) if root else None)
        )
    except scene_io.SceneIOError:
        duplicates = []
    for product_id in duplicates:
        report.error(
            "catalog.product_id.duplicate",
            "catalog/products.json",
            "Identyfikator produktu {!r} wystepuje wiecej niz raz.".format(product_id),
        )

    payload = report.as_dict()
    payload["scene_path"] = os.path.abspath(args.scene)
    payload["scene_id"] = scene.get("scene_id")
    payload["status"] = scene.get("status")
    payload["buildable"] = validate.is_buildable(scene, report)

    if args.out:
        scene_io.write_json(args.out, payload)

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_text_report(report, args.scene, args.quiet)
        if args.require_buildable and not payload["buildable"]:
            print(
                "\nScena nie nadaje sie do budowy: status={!r}, wymagany 'approved' "
                "i zero bledow.".format(scene.get("status"))
            )

    if not report.ok:
        return 1
    if args.require_buildable and not payload["buildable"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
