"""Walidacja sceny wzgledem kontraktu z docs/architecture.md.

Zasada nadrzedna: walidator nigdy nie naprawia danych po cichu.
Zglasza problem i pozostawia decyzje czlowiekowi.

Poziomy:
  ERROR   - scena jest niespojna, generator jej nie zbuduje.
  WARNING - scena sie zbuduje, ale wynik wymaga obejrzenia przez operatora.
  INFO    - obserwacja, nie blokuje niczego.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

from . import geometry as geo
from . import scene_io
from .constants import (
    AREA_ABSOLUTE_FLOOR_M2,
    AREA_ERROR_RATIO,
    AREA_WARNING_RATIO,
    BUILDABLE_STATUSES,
    COORDINATE_SYSTEM,
    EPS_M,
    MAX_ROOM_AREA_M2,
    MAX_ROOM_HEIGHT_M,
    MIN_ROOM_AREA_M2,
    MIN_ROOM_HEIGHT_M,
    OPENING_KINDS,
    SCENE_STATUSES,
    STATUS_APPROVED,
    SUPPORTED_SCHEMA_VERSIONS,
    UNITS,
)

ERROR = "ERROR"
WARNING = "WARNING"
INFO = "INFO"

_SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}


class Issue:
    """Pojedyncze zastrzezenie do sceny."""

    __slots__ = ("severity", "code", "path", "message")

    def __init__(self, severity: str, code: str, path: str, message: str) -> None:
        self.severity = severity
        self.code = code
        self.path = path
        self.message = message

    def __repr__(self) -> str:
        return "Issue({} {} {})".format(self.severity, self.code, self.path)

    def as_dict(self) -> Dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }

    def format_line(self) -> str:
        return "{:<7} {:<32} {}\n        {}".format(
            self.severity, self.code, self.path, self.message
        )


class Report:
    """Zbior zastrzezen wraz z podsumowaniem."""

    def __init__(self) -> None:
        self.issues: List[Issue] = []

    def add(self, severity: str, code: str, path: str, message: str) -> None:
        self.issues.append(Issue(severity, code, path, message))

    def error(self, code: str, path: str, message: str) -> None:
        self.add(ERROR, code, path, message)

    def warning(self, code: str, path: str, message: str) -> None:
        self.add(WARNING, code, path, message)

    def info(self, code: str, path: str, message: str) -> None:
        self.add(INFO, code, path, message)

    @property
    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == ERROR]

    @property
    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def sorted_issues(self) -> List[Issue]:
        return sorted(self.issues, key=lambda i: (_SEVERITY_ORDER[i.severity], i.path))

    def codes(self) -> List[str]:
        return [i.code for i in self.issues]

    def has(self, code: str) -> bool:
        return any(i.code == code for i in self.issues)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "counts": {
                "error": len(self.errors),
                "warning": len(self.warnings),
                "info": len(self.issues) - len(self.errors) - len(self.warnings),
            },
            "issues": [i.as_dict() for i in self.sorted_issues()],
        }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _positive(value: Any) -> bool:
    return _is_number(value) and value > EPS_M


def _check_header(scene: Dict[str, Any], report: Report) -> None:
    version = scene.get("schema_version")
    if version is None:
        report.error("header.schema_version.missing", "$", "Brak pola schema_version.")
    elif version not in SUPPORTED_SCHEMA_VERSIONS:
        report.error(
            "header.schema_version.unsupported",
            "$.schema_version",
            "Wersja {!r} nie jest obslugiwana. Obslugiwane: {}.".format(
                version, ", ".join(SUPPORTED_SCHEMA_VERSIONS)
            ),
        )

    scene_id = scene.get("scene_id")
    if not isinstance(scene_id, str) or not scene_id.strip():
        report.error("header.scene_id.missing", "$.scene_id", "scene_id musi byc niepustym tekstem.")
    elif not all(ch.isalnum() or ch in "-_" for ch in scene_id):
        report.error(
            "header.scene_id.charset",
            "$.scene_id",
            "scene_id sluzy jako nazwa katalogu; dozwolone sa litery, cyfry, - oraz _.",
        )

    if scene.get("units") != UNITS:
        report.error(
            "header.units",
            "$.units",
            "Kontrakt wymaga units={!r}, znaleziono {!r}.".format(UNITS, scene.get("units")),
        )

    if scene.get("coordinate_system") != COORDINATE_SYSTEM:
        report.error(
            "header.coordinate_system",
            "$.coordinate_system",
            "Kontrakt wymaga coordinate_system={!r}, znaleziono {!r}.".format(
                COORDINATE_SYSTEM, scene.get("coordinate_system")
            ),
        )

    status = scene.get("status")
    if status not in SCENE_STATUSES:
        report.error(
            "header.status",
            "$.status",
            "Status {!r} spoza listy: {}.".format(status, ", ".join(SCENE_STATUSES)),
        )

    sources = scene.get("sources")
    if not isinstance(sources, list):
        report.error("header.sources.type", "$.sources", "Pole sources musi byc lista.")
    elif not sources and status == STATUS_APPROVED:
        report.error(
            "header.sources.empty_when_approved",
            "$.sources",
            "Scena zatwierdzona musi wskazywac zrodla, z ktorych powstala geometria.",
        )
    elif not sources:
        report.warning(
            "header.sources.empty",
            "$.sources",
            "Brak zrodel. Bez nich nie da sie odtworzyc, skad wziely sie wymiary.",
        )


def _check_expected_area(
    room: Dict[str, Any], computed_m2: float, path: str, report: Report, strict: bool = True
) -> None:
    """Porownuje powierzchnie z wielokata z liczba przepisana z dokumentacji.

    To najtanszy dostepny test poprawnosci przepisania rzutu: jesli ktos
    pomyli sie o metr przy jednej scianie, powierzchnia natychmiast przestaje
    sie zgadzac. Pole jest opcjonalne - jego brak nie jest bledem, ale jego
    obecnosc zamienia "chyba dobrze przepisalem" w sprawdzalna liczbe.

    Powaga zalezy od statusu sceny. Szkic wolno miec niedokonczony - od tego
    jest szkicem, a generator ma go zbudowac, zeby bylo co ogladac i poprawiac.
    Scena zatwierdzona musi sie zgadzac, bo na niej opiera sie obietnica
    "wymiary sprawdzone".
    """
    expected = room.get("expected_area_m2")
    if expected is None:
        return
    if not _positive(expected):
        report.error(
            "room.expected_area.invalid",
            path + ".expected_area_m2",
            "expected_area_m2 musi byc liczba dodatnia albo nie moze go byc wcale.",
        )
        return

    difference = computed_m2 - expected
    absolute = abs(difference)
    if absolute <= AREA_ABSOLUTE_FLOOR_M2:
        return

    ratio = absolute / expected
    message = (
        "Z wielokata wychodzi {:.2f} m2, a dokumentacja podaje {:.2f} m2 "
        "(roznica {:+.2f} m2, {:.1f} %).".format(computed_m2, expected, difference, ratio * 100)
    )

    if ratio > AREA_ERROR_RATIO:
        tail = " Rzut przepisano blednie - popraw wielokat, nie liczbe."
        if strict:
            report.error("room.expected_area.mismatch", path + ".polygon_xy_m", message + tail)
        else:
            report.warning("room.expected_area.mismatch", path + ".polygon_xy_m", message + tail)
    elif ratio > AREA_WARNING_RATIO:
        report.warning(
            "room.expected_area.drift",
            path + ".polygon_xy_m",
            message + " Rozbieznosc w granicach zaokraglen, ale warto spojrzec.",
        )


def _check_room_polygon(room: Dict[str, Any], path: str, report: Report, strict: bool = True):
    raw = room.get("polygon_xy_m")
    if not isinstance(raw, list) or len(raw) < 3:
        report.error(
            "room.polygon.too_few_points",
            path + ".polygon_xy_m",
            "Wielokat pomieszczenia potrzebuje co najmniej 3 wierzcholkow.",
        )
        return None

    for index, point in enumerate(raw):
        if (
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or not all(_is_number(c) for c in point)
        ):
            report.error(
                "room.polygon.bad_point",
                "{}.polygon_xy_m[{}]".format(path, index),
                "Wierzcholek musi byc para liczb [x, y] w metrach.",
            )
            return None

    polygon = geo.as_points(raw)

    duplicates = geo.duplicate_vertices(polygon)
    if duplicates:
        report.error(
            "room.polygon.duplicate_vertices",
            path + ".polygon_xy_m",
            "Wierzcholki {} pokrywaja sie z nastepnym; sciana o zerowej dlugosci.".format(duplicates),
        )
        return None

    crossings = geo.self_intersections(polygon)
    if crossings:
        report.error(
            "room.polygon.self_intersection",
            path + ".polygon_xy_m",
            "Wielokat nie jest prosty; przecinaja sie sciany: {}.".format(
                ", ".join("{}x{}".format(a, b) for a, b in crossings)
            ),
        )
        return None

    room_area = geo.area(polygon)
    if room_area <= EPS_M:
        report.error("room.polygon.zero_area", path + ".polygon_xy_m", "Pole pomieszczenia wynosi zero.")
        return None

    _check_expected_area(room, room_area, path, report, strict)
    if room_area < MIN_ROOM_AREA_M2:
        report.warning(
            "room.polygon.tiny",
            path + ".polygon_xy_m",
            "Pole {:.2f} m2 jest podejrzanie male - sprawdz jednostki rzutu.".format(room_area),
        )
    if room_area > MAX_ROOM_AREA_M2:
        report.warning(
            "room.polygon.huge",
            path + ".polygon_xy_m",
            "Pole {:.2f} m2 jest podejrzanie duze - sprawdz skale rzutu.".format(room_area),
        )

    if not geo.is_ccw(polygon):
        report.info(
            "room.polygon.clockwise",
            path + ".polygon_xy_m",
            "Wierzcholki zapisane zgodnie z ruchem wskazowek zegara. "
            "Generator odwroci kolejnosc, ale wall_index pozostaje wg pliku.",
        )

    return polygon


def _check_openings(
    room: Dict[str, Any], polygon: Sequence, height_m: Any, path: str, report: Report
) -> None:
    openings = room.get("openings", [])
    if not isinstance(openings, list):
        report.error("room.openings.type", path + ".openings", "Pole openings musi byc lista.")
        return

    lengths = geo.wall_lengths(polygon)
    per_wall: Dict[int, List] = {}

    for index, opening in enumerate(openings):
        opening_path = "{}.openings[{}]".format(path, index)
        if not isinstance(opening, dict):
            report.error("opening.type", opening_path, "Otwor musi byc obiektem JSON.")
            continue

        kind = opening.get("kind")
        if kind not in OPENING_KINDS:
            report.error(
                "opening.kind",
                opening_path + ".kind",
                "Rodzaj {!r} spoza listy: {}.".format(kind, ", ".join(OPENING_KINDS)),
            )

        wall_index = opening.get("wall_index")
        if not isinstance(wall_index, int) or isinstance(wall_index, bool):
            report.error(
                "opening.wall_index.type",
                opening_path + ".wall_index",
                "wall_index musi byc liczba calkowita.",
            )
            continue
        if not 0 <= wall_index < len(lengths):
            report.error(
                "opening.wall_index.range",
                opening_path + ".wall_index",
                "Sciana {} nie istnieje; pomieszczenie ma {} scian (0-{}).".format(
                    wall_index, len(lengths), len(lengths) - 1
                ),
            )
            continue

        wall_length = lengths[wall_index]
        offset = opening.get("offset_m")
        width = opening.get("width_m")
        sill = opening.get("sill_m")
        opening_height = opening.get("height_m")

        if not _is_number(offset) or offset < -EPS_M:
            report.error(
                "opening.offset.invalid",
                opening_path + ".offset_m",
                "offset_m musi byc liczba nieujemna.",
            )
            continue
        if not _positive(width):
            report.error(
                "opening.width.invalid", opening_path + ".width_m", "width_m musi byc liczba dodatnia."
            )
            continue
        if offset + width > wall_length + EPS_M:
            report.error(
                "opening.exceeds_wall",
                opening_path,
                "Otwor konczy sie na {:.3f} m, a sciana {} ma {:.3f} m.".format(
                    offset + width, wall_index, wall_length
                ),
            )
            continue

        if not _is_number(sill) or sill < -EPS_M:
            report.error(
                "opening.sill.invalid", opening_path + ".sill_m", "sill_m musi byc liczba nieujemna."
            )
            continue
        if not _positive(opening_height):
            report.error(
                "opening.height.invalid",
                opening_path + ".height_m",
                "height_m musi byc liczba dodatnia.",
            )
            continue
        if _is_number(height_m) and sill + opening_height > height_m + EPS_M:
            report.error(
                "opening.exceeds_room_height",
                opening_path,
                "Gora otworu na {:.3f} m przekracza wysokosc pomieszczenia {:.3f} m.".format(
                    sill + opening_height, height_m
                ),
            )
            continue

        if kind == "door" and sill > EPS_M:
            report.warning(
                "opening.door.raised_sill",
                opening_path + ".sill_m",
                "Drzwi z progiem {:.3f} m. Zamierzone czy blad odczytu rzutu?".format(sill),
            )
        if kind == "window" and sill <= EPS_M:
            report.warning(
                "opening.window.floor_level",
                opening_path + ".sill_m",
                "Okno zaczyna sie na poziomie podlogi. Jesli to portfenetr, opisz to w evidence.",
            )

        per_wall.setdefault(wall_index, []).append((offset, offset + width, index))

    for wall_index, spans in per_wall.items():
        spans.sort()
        for earlier, later in zip(spans, spans[1:]):
            if later[0] < earlier[1] - EPS_M:
                report.error(
                    "opening.overlap",
                    "{}.openings[{}]".format(path, later[2]),
                    "Otwory {} i {} nachodza na siebie na scianie {}.".format(
                        earlier[2], later[2], wall_index
                    ),
                )


def _check_rooms(scene: Dict[str, Any], report: Report) -> Dict[str, Any]:
    strict = scene.get("status") == STATUS_APPROVED
    rooms = scene.get("rooms")
    geometry_by_room: Dict[str, Any] = {}

    if not isinstance(rooms, list) or not rooms:
        report.error(
            "scene.rooms.empty", "$.rooms", "Scena musi zawierac co najmniej jedno pomieszczenie."
        )
        return geometry_by_room

    seen_ids: Dict[str, int] = {}
    for index, room in enumerate(rooms):
        path = "$.rooms[{}]".format(index)
        if not isinstance(room, dict):
            report.error("room.type", path, "Pomieszczenie musi byc obiektem JSON.")
            continue

        room_id = room.get("id")
        if not isinstance(room_id, str) or not room_id.strip():
            report.error("room.id.missing", path + ".id", "Pomieszczenie musi miec niepuste id.")
            room_id = None
        else:
            seen_ids[room_id] = seen_ids.get(room_id, 0) + 1
            if seen_ids[room_id] > 1:
                report.error(
                    "room.id.duplicate", path + ".id", "Identyfikator {!r} juz wystapil.".format(room_id)
                )

        height_m = room.get("height_m")
        if not _positive(height_m):
            report.error("room.height.invalid", path + ".height_m", "height_m musi byc liczba dodatnia.")
            height_m = None
        elif height_m < MIN_ROOM_HEIGHT_M or height_m > MAX_ROOM_HEIGHT_M:
            report.warning(
                "room.height.unusual",
                path + ".height_m",
                "Wysokosc {:.2f} m poza typowym zakresem {:.1f}-{:.1f} m.".format(
                    height_m, MIN_ROOM_HEIGHT_M, MAX_ROOM_HEIGHT_M
                ),
            )

        polygon = _check_room_polygon(room, path, report, strict)
        if polygon is not None:
            _check_openings(room, polygon, height_m, path, report)
            if room_id:
                geometry_by_room[room_id] = {"polygon": polygon, "height_m": height_m}

        evidence = room.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            report.warning(
                "room.evidence.missing",
                path + ".evidence",
                "Brak opisu, skad pochodza wymiary tego pomieszczenia.",
            )

    return geometry_by_room


def _check_furniture(
    scene: Dict[str, Any],
    catalog: Dict[str, Dict[str, Any]],
    geometry_by_room: Dict[str, Any],
    report: Report,
    root: Optional[str],
    check_models: bool,
) -> Dict[str, Any]:
    furniture = scene.get("furniture", [])
    placed: Dict[str, Any] = {}

    if not isinstance(furniture, list):
        report.error("scene.furniture.type", "$.furniture", "Pole furniture musi byc lista.")
        return placed

    seen_ids: Dict[str, int] = {}
    for index, item in enumerate(furniture):
        path = "$.furniture[{}]".format(index)
        if not isinstance(item, dict):
            report.error("furniture.type", path, "Mebel musi byc obiektem JSON.")
            continue

        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            report.error("furniture.id.missing", path + ".id", "Mebel musi miec niepuste id.")
            item_id = None
        else:
            seen_ids[item_id] = seen_ids.get(item_id, 0) + 1
            if seen_ids[item_id] > 1:
                report.error(
                    "furniture.id.duplicate",
                    path + ".id",
                    "Identyfikator {!r} juz wystapil.".format(item_id),
                )

        product_id = item.get("product_id")
        product = None
        if not isinstance(product_id, str) or not product_id.strip():
            report.error("furniture.product_id.missing", path + ".product_id", "Brak product_id.")
        elif product_id not in catalog:
            report.error(
                "furniture.product_id.unknown",
                path + ".product_id",
                "Produkt {!r} nie wystepuje w catalog/products.json.".format(product_id),
            )
        else:
            product = catalog[product_id]
            if not product.get("license"):
                report.error(
                    "product.license.missing",
                    path + ".product_id",
                    "Produkt {!r} nie ma zapisanej licencji. Bez tego nie wolno go uzyc.".format(
                        product_id
                    ),
                )
            if check_models:
                model_path = scene_io.resolve_model_path(product, root)
                if model_path is None:
                    report.error(
                        "product.model_path.missing",
                        path + ".product_id",
                        "Produkt {!r} nie wskazuje pliku modelu.".format(product_id),
                    )
                elif not os.path.isfile(model_path):
                    report.error(
                        "product.model_path.not_found",
                        path + ".product_id",
                        "Plik modelu nie istnieje: {}".format(model_path),
                    )

        position = item.get("position_m")
        if (
            not isinstance(position, (list, tuple))
            or len(position) != 3
            or not all(_is_number(c) for c in position)
        ):
            report.error(
                "furniture.position.invalid",
                path + ".position_m",
                "position_m musi byc lista trzech liczb [x, y, z] w metrach.",
            )
            continue

        rotation = item.get("rotation_deg", 0.0)
        if not _is_number(rotation):
            report.error(
                "furniture.rotation.invalid", path + ".rotation_deg", "rotation_deg musi byc liczba."
            )
            continue

        if position[2] < -EPS_M:
            report.warning(
                "furniture.below_floor",
                path + ".position_m",
                "Mebel zaczyna sie ponizej poziomu podlogi (z={:.3f}).".format(position[2]),
            )

        room_id = item.get("room_id")
        if isinstance(room_id, str) and room_id in geometry_by_room:
            polygon = geometry_by_room[room_id]["polygon"]
            if not geo.point_in_polygon(polygon, (position[0], position[1])):
                report.error(
                    "furniture.outside_room",
                    path + ".position_m",
                    "Punkt ({:.2f}, {:.2f}) lezy poza obrysem pomieszczenia {!r}.".format(
                        position[0], position[1], room_id
                    ),
                )
        elif isinstance(room_id, str):
            report.error(
                "furniture.room_id.unknown",
                path + ".room_id",
                "Pomieszczenie {!r} nie istnieje w tej scenie.".format(room_id),
            )
        elif room_id is not None:
            report.error("furniture.room_id.type", path + ".room_id", "room_id musi byc tekstem.")

        dimensions = (product or {}).get("dimensions_m")
        footprint = None
        if isinstance(dimensions, dict):
            size_x = dimensions.get("x")
            size_y = dimensions.get("y")
            if _positive(size_x) and _positive(size_y):
                footprint = geo.footprint_corners(
                    (position[0], position[1]), float(size_x), float(size_y), float(rotation)
                )

        if item_id:
            placed[item_id] = {
                "path": path,
                "footprint": footprint,
                "room_id": room_id if isinstance(room_id, str) else None,
            }

    ids = list(placed.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            first, second = placed[ids[i]], placed[ids[j]]
            if first["footprint"] is None or second["footprint"] is None:
                continue
            if first["room_id"] != second["room_id"]:
                continue
            if geo.rects_overlap(first["footprint"], second["footprint"]):
                report.warning(
                    "furniture.overlap",
                    second["path"],
                    "Rzuty mebli {!r} i {!r} nachodza na siebie.".format(ids[i], ids[j]),
                )

    return placed


def _check_variants(
    scene: Dict[str, Any],
    catalog: Dict[str, Dict[str, Any]],
    placed: Dict[str, Any],
    report: Report,
) -> None:
    variants = scene.get("variants", [])
    if not isinstance(variants, list):
        report.error("scene.variants.type", "$.variants", "Pole variants musi byc lista.")
        return

    seen_ids: Dict[str, int] = {}
    for index, variant in enumerate(variants):
        path = "$.variants[{}]".format(index)
        if not isinstance(variant, dict):
            report.error("variant.type", path, "Wariant musi byc obiektem JSON.")
            continue

        variant_id = variant.get("id")
        if not isinstance(variant_id, str) or not variant_id.strip():
            report.error("variant.id.missing", path + ".id", "Wariant musi miec niepuste id.")
        else:
            seen_ids[variant_id] = seen_ids.get(variant_id, 0) + 1
            if seen_ids[variant_id] > 1:
                report.error(
                    "variant.id.duplicate",
                    path + ".id",
                    "Identyfikator {!r} juz wystapil.".format(variant_id),
                )

        substitutions = variant.get("substitutions", [])
        if not isinstance(substitutions, list):
            report.error(
                "variant.substitutions.type",
                path + ".substitutions",
                "Pole substitutions musi byc lista.",
            )
            continue

        for sub_index, substitution in enumerate(substitutions):
            sub_path = "{}.substitutions[{}]".format(path, sub_index)
            if not isinstance(substitution, dict):
                report.error("variant.substitution.type", sub_path, "Podmiana musi byc obiektem JSON.")
                continue
            target = substitution.get("furniture_id")
            replacement = substitution.get("product_id")
            if not isinstance(target, str) or target not in placed:
                report.error(
                    "variant.substitution.unknown_furniture",
                    sub_path + ".furniture_id",
                    "Mebel {!r} nie wystepuje w scenie.".format(target),
                )
            if not isinstance(replacement, str) or replacement not in catalog:
                report.error(
                    "variant.substitution.unknown_product",
                    sub_path + ".product_id",
                    "Produkt {!r} nie wystepuje w katalogu.".format(replacement),
                )

    if len(variants) == 1:
        report.info(
            "scene.variants.single",
            "$.variants",
            "Zakres MVP zaklada dwa warianty tej samej sceny; jest jeden.",
        )


def validate_scene(
    scene: Dict[str, Any],
    catalog: Optional[Dict[str, Dict[str, Any]]] = None,
    root: Optional[str] = None,
    check_models: bool = True,
) -> Report:
    """Sprawdza scene i zwraca raport. Nie modyfikuje danych wejsciowych."""
    report = Report()
    catalog = catalog if catalog is not None else {}

    _check_header(scene, report)
    geometry_by_room = _check_rooms(scene, report)
    placed = _check_furniture(scene, catalog, geometry_by_room, report, root, check_models)
    _check_variants(scene, catalog, placed, report)

    if scene.get("status") == STATUS_APPROVED and report.warnings:
        report.error(
            "scene.approved_with_warnings",
            "$.status",
            "Scena ma status approved przy {} ostrzezeniach. Operator musi je rozwiazac "
            "albo opisac w review_notes przed budowa.".format(len(report.warnings)),
        )

    return report


def is_buildable(scene: Dict[str, Any], report: Report) -> bool:
    """Czy scene wolno przekazac do generatora produkcyjnego."""
    return report.ok and scene.get("status") in BUILDABLE_STATUSES
