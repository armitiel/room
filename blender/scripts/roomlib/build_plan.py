"""Plan budowy sceny: liczby przed geometria.

Ten modul zamienia zatwierdzony scene.json na jednoznaczny opis bryl
do zbudowania - i robi to bez Blendera. Dzieki temu da sie sprawdzic
wymiary, naroza i otwory w zwyklym tescie jednostkowym, zanim ktokolwiek
uruchomi silnik.

build_scene.py wykonuje juz tylko mechaniczne tworzenie siatek wg tego planu.

Uklad: metry, Z w gore, z=0 to poziom podlogi wykonczonej.
Wielokat z pliku opisuje WEWNETRZNE lico scian, wiec sciany rosna na zewnatrz
i wymiary w swietle zgadzaja sie z rzutem.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import geometry as geo
from .constants import (
    DEFAULT_WALL_THICKNESS_M,
    DOOR_LEAF_THICKNESS_M,
    EPS_M,
    FRAME_WIDTH_M,
    GLASS_THICKNESS_M,
)

Point = Tuple[float, float]


class BuildPlanError(Exception):
    """Nie da sie zbudowac planu z podanych danych."""


def _line_intersection(p1: Point, d1: Point, p2: Point, d2: Point) -> Optional[Point]:
    """Przeciecie dwoch prostych zadanych punktem i kierunkiem."""
    denominator = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(denominator) <= 1e-9:
        return None
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    t = (dx * d2[1] - dy * d2[0]) / denominator
    return (p1[0] + d1[0] * t, p1[1] + d1[1] * t)


def outward_normals(polygon: Sequence[Point]) -> List[Point]:
    """Normalne scian skierowane na zewnatrz pomieszczenia (wielokat CCW)."""
    result = []
    for (x1, y1), (x2, y2) in geo.walls(polygon):
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length <= EPS_M:
            raise BuildPlanError("Sciana o zerowej dlugosci - najpierw uruchom walidator.")
        result.append((dy / length, -dx / length))
    return result


def offset_polygon(polygon: Sequence[Point], distance: float) -> List[Point]:
    """Wielokat odsuniety na zewnatrz o zadana odleglosc, z narozami na styk.

    Naroza liczone sa jako przeciecie odsunietych prostych (polaczenie zaciosowe),
    wiec sciany stykaja sie bez szczelin i bez zakladek zarowno w narozach
    wypuklych, jak i wkleslych.
    """
    pts = list(polygon)
    n = len(pts)
    normals = outward_normals(pts)
    segments = geo.walls(pts)

    offset_lines = []
    for index, ((x1, y1), (x2, y2)) in enumerate(segments):
        nx, ny = normals[index]
        base = (x1 + nx * distance, y1 + ny * distance)
        direction = (x2 - x1, y2 - y1)
        offset_lines.append((base, direction))

    result: List[Point] = []
    for index in range(n):
        previous = offset_lines[(index - 1) % n]
        current = offset_lines[index]
        crossing = _line_intersection(previous[0], previous[1], current[0], current[1])
        if crossing is None:
            # Sciany wspolliniowe - odsuwamy wierzcholek prostopadle.
            nx, ny = normals[index]
            crossing = (pts[index][0] + nx * distance, pts[index][1] + ny * distance)
        result.append(crossing)
    return result


def plan_walls(
    polygon: Sequence[Point], height_m: float, thickness_m: float
) -> List[Dict[str, Any]]:
    """Sciany jako pryzmy o podstawie czworokatnej.

    Podstawa sciany i to: inner[i], inner[i+1], outer[i+1], outer[i].
    """
    inner = geo.ensure_ccw(polygon)
    reversed_order = inner != list(polygon)
    outer = offset_polygon(inner, thickness_m)
    n = len(inner)

    walls: List[Dict[str, Any]] = []
    for index in range(n):
        nxt = (index + 1) % n
        # Po odwroceniu kolejnosci wierzcholkow sciana index odpowiada
        # krawedzi (n - 2 - index) z pliku i jest przebiegana w druga strone.
        source_index = (n - 2 - index) % n if reversed_order else index
        walls.append(
            {
                "index": index,
                "source_wall_index": source_index,
                "source_reversed": reversed_order,
                "base": [inner[index], inner[nxt], outer[nxt], outer[index]],
                "inner_start": inner[index],
                "inner_end": inner[nxt],
                "length_m": geo.segment_length((inner[index], inner[nxt])),
                "angle_deg": geo.wall_angle_deg((inner[index], inner[nxt])),
                "height_m": height_m,
                "thickness_m": thickness_m,
            }
        )
    return walls


def plan_opening_cut(
    wall: Dict[str, Any], opening: Dict[str, Any], overshoot_m: float = 0.05
) -> Dict[str, Any]:
    """Prostopadloscian do odjecia od sciany.

    Bryla wystaje poza obie strony sciany o overshoot_m, bo boolean na
    dokladnie stykajacych sie licach zostawia w Blenderze artefakty.
    """
    offset = float(opening["offset_m"])
    width = float(opening["width_m"])
    sill = float(opening["sill_m"])
    height = float(opening["height_m"])
    thickness = float(wall["thickness_m"])

    segment = (wall["inner_start"], wall["inner_end"])
    # offset_m liczy sie od poczatku sciany TAK JAK ZAPISANO W PLIKU.
    # Jesli generator przebiega te sciane w druga strone, odleglosc
    # trzeba odbic, inaczej otwor wyladuje po przeciwnej stronie sciany.
    if wall.get("source_reversed"):
        center_along = wall["length_m"] - (offset + width / 2.0)
    else:
        center_along = offset + width / 2.0
    anchor = geo.point_on_wall(segment, center_along)

    # Srodek bryly przesuniety na polowe grubosci sciany, czyli na zewnatrz.
    normal = geo.wall_normal(segment)  # do wnetrza
    center_x = anchor[0] - normal[0] * thickness / 2.0
    center_y = anchor[1] - normal[1] * thickness / 2.0

    return {
        "wall_index": wall["index"],
        "kind": opening.get("kind"),
        "center_m": (center_x, center_y, sill + height / 2.0),
        "size_m": (width, thickness + 2 * overshoot_m, height),
        "rotation_deg": wall["angle_deg"],
    }


def plan_room(room: Dict[str, Any], thickness_m: float = DEFAULT_WALL_THICKNESS_M) -> Dict[str, Any]:
    """Kompletny plan jednego pomieszczenia."""
    polygon = geo.as_points(room["polygon_xy_m"])
    height_m = float(room["height_m"])
    walls = plan_walls(polygon, height_m, thickness_m)

    by_source = {wall["source_wall_index"]: wall for wall in walls}
    cuts: List[Dict[str, Any]] = []
    joinery: List[Dict[str, Any]] = []
    for opening in room.get("openings", []) or []:
        wall = by_source.get(opening["wall_index"])
        if wall is None:
            raise BuildPlanError(
                "Otwor wskazuje sciane {}, ktorej nie ma w planie.".format(opening["wall_index"])
            )
        cut = plan_opening_cut(wall, opening)
        cuts.append(cut)
        joinery.extend(plan_joinery(wall, opening, cut))

    return {
        "room_id": room.get("id"),
        "polygon": geo.ensure_ccw(polygon),
        "height_m": height_m,
        "thickness_m": thickness_m,
        "floor_area_m2": geo.area(polygon),
        "walls": walls,
        "openings": cuts,
        "joinery": joinery,
    }


def plan_furniture(
    scene: Dict[str, Any], catalog: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Lista mebli do wstawienia wraz z danymi produktu."""
    items = []
    for item in scene.get("furniture", []) or []:
        product = catalog.get(item.get("product_id"), {})
        position = item["position_m"]
        items.append(
            {
                "id": item.get("id"),
                "product_id": item.get("product_id"),
                "room_id": item.get("room_id"),
                "location_m": (float(position[0]), float(position[1]), float(position[2])),
                "rotation_deg": float(item.get("rotation_deg", 0.0)),
                "model_path": product.get("model_path"),
                "dimensions_m": product.get("dimensions_m"),
            }
        )
    return items


def plan_scene(
    scene: Dict[str, Any],
    catalog: Optional[Dict[str, Dict[str, Any]]] = None,
    thickness_m: float = DEFAULT_WALL_THICKNESS_M,
) -> Dict[str, Any]:
    """Plan calej sceny. Deterministyczny: te same dane dadza ten sam plan."""
    catalog = catalog or {}
    rooms = [plan_room(room, thickness_m) for room in scene.get("rooms", [])]
    return {
        "scene_id": scene.get("scene_id"),
        "status": scene.get("status"),
        "wall_thickness_m": thickness_m,
        "rooms": rooms,
        "furniture": plan_furniture(scene, catalog),
        "variants": scene.get("variants", []) or [],
        "totals": {
            "rooms": len(rooms),
            "walls": sum(len(room["walls"]) for room in rooms),
            "openings": sum(len(room["openings"]) for room in rooms),
            "joinery": sum(len(room["joinery"]) for room in rooms),
            "furniture": len(scene.get("furniture", []) or []),
            "floor_area_m2": round(sum(room["floor_area_m2"] for room in rooms), 3),
        },
    }


def plan_joinery(
    wall: Dict[str, Any],
    opening: Dict[str, Any],
    cut: Dict[str, Any],
    frame_width_m: float = FRAME_WIDTH_M,
) -> List[Dict[str, Any]]:
    """Stolarka jednego otworu: oscieznica, parapet, szyba, skrzydlo.

    Otwor wyciety booleanem jest dziura w scianie i tak tez wyglada.
    Rama wypelnia oscieze, szyba zamyka pole, a drzwi zewnetrzne dostaja
    skrzydlo. Elementy sa liczone w ukladzie lokalnym sciany (x wzdluz,
    y w poprzek, z w gore), a potem obracane o kat sciany - dzieki temu
    ta funkcja nie wie nic o Blenderze i da sie ja sprawdzic testem.

    Zwraca liste bryl: name, role, center_m, size_m, rotation_deg.
    """
    kind = opening.get("kind")
    if kind == "passage":
        return []  # otwarcie miedzy pomieszczeniami nie ma stolarki

    width = float(opening["width_m"])
    height = float(opening["height_m"])
    sill = float(opening["sill_m"])
    thickness = float(wall["thickness_m"])
    angle = float(cut["rotation_deg"])
    centre_x, centre_y, _ = cut["center_m"]
    frame = min(frame_width_m, width / 3.0, height / 3.0)

    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def place(name, role, lx, lz, size_x, size_y, size_z):
        return {
            "name": name,
            "role": role,
            "center_m": (centre_x + lx * cos_a, centre_y + lx * sin_a, lz),
            "size_m": (size_x, size_y, size_z),
            "rotation_deg": angle,
        }

    pieces: List[Dict[str, Any]] = []
    half = width / 2.0
    top = sill + height
    has_sill = kind == "window"

    # Okna i drzwi dostaja osobne role, bo w budynku sa z innego materialu:
    # stolarka okienna zwykle ciemna, oscieznice drzwiowe biale.
    frame_role = "frame_window" if kind == "window" else "frame_door"

    # Boczne oscieznice na pelna wysokosc otworu.
    for side, sign in (("left", -1.0), ("right", 1.0)):
        pieces.append(
            place(
                "jamb_" + side, frame_role,
                sign * (half - frame / 2.0), sill + height / 2.0,
                frame, thickness, height,
            )
        )

    inner_width = max(width - 2 * frame, 0.0)

    # Nadproze.
    pieces.append(place("head", frame_role, 0.0, top - frame / 2.0, inner_width, thickness, frame))

    if has_sill:
        pieces.append(place("sill", frame_role, 0.0, sill + frame / 2.0, inner_width, thickness, frame))

    inner_bottom = sill + frame if has_sill else sill
    inner_height = max(top - frame - inner_bottom, 0.0)
    inner_centre_z = inner_bottom + inner_height / 2.0

    if kind == "window" and inner_width > 0 and inner_height > 0:
        pieces.append(
            place("glass", "glass", 0.0, inner_centre_z, inner_width, GLASS_THICKNESS_M, inner_height)
        )
    elif kind == "door" and inner_width > 0 and inner_height > 0 and opening.get("leaf", False):
        pieces.append(
            place("leaf", "leaf", 0.0, inner_centre_z, inner_width, DOOR_LEAF_THICKNESS_M, inner_height)
        )

    return pieces
