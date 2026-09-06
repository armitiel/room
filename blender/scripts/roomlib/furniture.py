"""Parametryczne bryly meblowe.

Meble opisujemy jako zestaw prostopadloscianow liczonych z gabarytow produktu,
a nie jako gotowe pliki modeli. Powody sa trzy: nie mamy jeszcze licencji na
modele producentow, bryla o poprawnych wymiarach juz odpowiada na pytanie
"czy to sie tu zmiesci", a plik wynikowy zostaje maly.

Kazdy generator dostaje wymiary z katalogu i zwraca liste czesci w ukladzie
LOKALNYM mebla: srodek w rzucie, zero na poziomie podlogi, os X wzdluz
szerokosci, Y w glab, Z w gore. Obrot i przesuniecie dokleja build_plan.

Czesc niesie role materialowa, dzieki czemu wariant wykonczenia zmienia
tapicerke i drewno tak samo, jak zmienia podloge.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

Part = Dict[str, Any]

# Role materialowe czesci meblowych.
SOFT = "furniture_soft"      # tapicerka
WOOD = "furniture_wood"      # drewno, fronty
PANEL = "furniture_panel"    # lakier, plyta
STONE = "furniture_stone"    # blat, ceramika
METAL = "furniture_metal"    # nogi, uchwyty


def _part(name: str, role: str, cx: float, cy: float, cz: float,
          sx: float, sy: float, sz: float) -> Part:
    return {
        "name": name,
        "role": role,
        "center_m": (cx, cy, cz),
        "size_m": (max(sx, 0.001), max(sy, 0.001), max(sz, 0.001)),
    }


def _legs(role: str, width: float, depth: float, height: float,
          inset: float = 0.08, thickness: float = 0.05) -> List[Part]:
    parts = []
    x = width / 2 - inset - thickness / 2
    y = depth / 2 - inset - thickness / 2
    for index, (sx, sy) in enumerate(((-x, -y), (x, -y), (x, y), (-x, y))):
        parts.append(_part("leg_%d" % index, role, sx, sy, height / 2, thickness, thickness, height))
    return parts


def sofa(width: float, depth: float, height: float) -> List[Part]:
    """Sofa: podstawa, oparcie, dwa boki, poduszki siedziska."""
    seat_h = height * 0.42
    back_t = depth * 0.18
    arm_w = width * 0.09

    parts = [
        _part("base", SOFT, 0.0, 0.0, seat_h * 0.45, width, depth, seat_h * 0.9),
        _part("back", SOFT, 0.0, depth / 2 - back_t / 2, height / 2, width, back_t, height),
        _part("arm_left", SOFT, -width / 2 + arm_w / 2, -back_t / 2, height * 0.33,
              arm_w, depth - back_t, height * 0.66),
        _part("arm_right", SOFT, width / 2 - arm_w / 2, -back_t / 2, height * 0.33,
              arm_w, depth - back_t, height * 0.66),
    ]

    cushions = max(2, int(round((width - 2 * arm_w) / 0.62)))
    inner = width - 2 * arm_w - 0.04
    cushion_w = inner / cushions
    for index in range(cushions):
        cx = -inner / 2 + cushion_w * (index + 0.5)
        parts.append(
            _part("cushion_%d" % index, SOFT, cx, -back_t / 2, seat_h + 0.05,
                  cushion_w - 0.03, depth - back_t - 0.06, 0.12)
        )
    parts += _legs(METAL, width, depth, seat_h * 0.18, inset=0.06, thickness=0.05)
    return parts


def armchair(width: float, depth: float, height: float) -> List[Part]:
    return sofa(width, depth, height)


def bed(width: float, depth: float, height: float) -> List[Part]:
    """Lozko: rama, materac, zaglowek, poduszki."""
    frame_h = height * 0.32
    mattress_h = height * 0.30
    head_h = height

    parts = [
        _part("frame", WOOD, 0.0, 0.0, frame_h / 2, width, depth, frame_h),
        _part("mattress", SOFT, 0.0, 0.0, frame_h + mattress_h / 2,
              width - 0.04, depth - 0.04, mattress_h),
        _part("headboard", SOFT, 0.0, depth / 2 - 0.04, head_h / 2, width, 0.08, head_h),
    ]
    pillow_w = min(0.55, (width - 0.15) / 2)
    for index, side in enumerate((-1, 1)):
        parts.append(
            _part("pillow_%d" % index, SOFT, side * (pillow_w / 2 + 0.03),
                  depth / 2 - 0.30, frame_h + mattress_h + 0.05,
                  pillow_w, 0.36, 0.10)
        )
    return parts


def wardrobe(width: float, depth: float, height: float) -> List[Part]:
    """Szafa: korpus i fronty rozdzielone szczelina, zeby czytac podzialy."""
    parts = [_part("body", PANEL, 0.0, 0.02, height / 2, width, depth - 0.04, height)]
    doors = max(2, int(round(width / 0.6)))
    door_w = width / doors
    for index in range(doors):
        cx = -width / 2 + door_w * (index + 0.5)
        parts.append(
            _part("door_%d" % index, WOOD, cx, -depth / 2 + 0.01, height / 2,
                  door_w - 0.012, 0.02, height - 0.03)
        )
    return parts


def table(width: float, depth: float, height: float) -> List[Part]:
    top = 0.04
    parts = [_part("top", WOOD, 0.0, 0.0, height - top / 2, width, depth, top)]
    parts += _legs(WOOD, width, depth, height - top, inset=0.10, thickness=0.06)
    return parts


def chair(width: float, depth: float, height: float) -> List[Part]:
    seat_h = 0.45
    parts = [
        _part("seat", WOOD, 0.0, 0.0, seat_h, width, depth, 0.04),
        _part("back", WOOD, 0.0, depth / 2 - 0.03, seat_h + (height - seat_h) / 2,
              width, 0.04, height - seat_h),
    ]
    parts += _legs(WOOD, width, depth, seat_h - 0.02, inset=0.04, thickness=0.04)
    return parts


def kitchen_run(width: float, depth: float, height: float) -> List[Part]:
    """Zabudowa kuchenna: szafki dolne, blat, szafki gorne."""
    worktop = 0.04
    base_h = height - worktop      # gabaryt z katalogu to wysokosc blatu
    upper_h = 0.72
    upper_z = height + 0.55        # odstep nad blatem wg praktyki kuchennej

    parts = [
        _part("base", PANEL, 0.0, 0.0, base_h / 2, width, depth, base_h),
        _part("worktop", STONE, 0.0, 0.0, base_h + worktop / 2, width, depth, worktop),
        _part("upper", PANEL, 0.0, depth * 0.15, upper_z + upper_h / 2,
              width, depth * 0.62, upper_h),
    ]
    fronts = max(2, int(round(width / 0.6)))
    front_w = width / fronts
    for index in range(fronts):
        cx = -width / 2 + front_w * (index + 0.5)
        parts.append(
            _part("front_%d" % index, WOOD, cx, -depth / 2 + 0.01, base_h / 2,
                  front_w - 0.012, 0.02, base_h - 0.06)
        )
    return parts


def counter(width: float, depth: float, height: float) -> List[Part]:
    """Wyspa albo lada: korpus z blatem."""
    worktop = 0.04
    return [
        _part("body", PANEL, 0.0, 0.0, (height - worktop) / 2, width, depth, height - worktop),
        _part("worktop", STONE, 0.0, 0.0, height - worktop / 2, width + 0.04, depth + 0.04, worktop),
    ]


def wc(width: float, depth: float, height: float) -> List[Part]:
    return [
        _part("bowl", STONE, 0.0, -depth * 0.14, 0.20, width, depth * 0.72, 0.40),
        _part("cistern", STONE, 0.0, depth / 2 - 0.09, height / 2, width * 0.86, 0.18, height),
    ]


def basin(width: float, depth: float, height: float) -> List[Part]:
    return [
        _part("cabinet", WOOD, 0.0, 0.0, (height - 0.12) / 2, width, depth, height - 0.12),
        _part("bowl", STONE, 0.0, 0.0, height - 0.06, width * 0.92, depth * 0.86, 0.12),
    ]


def bathtub(width: float, depth: float, height: float) -> List[Part]:
    wall = 0.07
    return [
        _part("body", STONE, 0.0, 0.0, height / 2, width, depth, height),
        _part("water", STONE, 0.0, 0.0, height - 0.02, width - 2 * wall, depth - 2 * wall, 0.04),
    ]


def shower(width: float, depth: float, height: float) -> List[Part]:
    return [
        _part("tray", STONE, 0.0, 0.0, 0.04, width, depth, 0.08),
        _part("glass", METAL, 0.0, -depth / 2 + 0.01, height / 2, width, 0.02, height),
    ]


def rug(width: float, depth: float, height: float) -> List[Part]:
    return [_part("rug", SOFT, 0.0, 0.0, 0.006, width, depth, 0.012)]


def sideboard(width: float, depth: float, height: float) -> List[Part]:
    parts = [_part("body", PANEL, 0.0, 0.0, height / 2, width, depth, height)]
    fronts = max(2, int(round(width / 0.55)))
    front_w = width / fronts
    for index in range(fronts):
        cx = -width / 2 + front_w * (index + 0.5)
        parts.append(
            _part("front_%d" % index, WOOD, cx, -depth / 2 + 0.01, height / 2,
                  front_w - 0.012, 0.02, height - 0.04)
        )
    return parts


PRIMITIVES: Dict[str, Callable[[float, float, float], List[Part]]] = {
    "sofa": sofa,
    "armchair": armchair,
    "bed": bed,
    "wardrobe": wardrobe,
    "table": table,
    "chair": chair,
    "kitchen_run": kitchen_run,
    "counter": counter,
    "wc": wc,
    "basin": basin,
    "bathtub": bathtub,
    "shower": shower,
    "rug": rug,
    "sideboard": sideboard,
}

FURNITURE_ROLES = (SOFT, WOOD, PANEL, STONE, METAL)


def build(primitive: str, dimensions: Dict[str, float]) -> List[Part]:
    """Czesci mebla dla podanego rodzaju i gabarytow z katalogu."""
    if primitive not in PRIMITIVES:
        raise KeyError("Nieznana bryla meblowa: {}".format(primitive))
    width = float(dimensions.get("x", 0.5))
    depth = float(dimensions.get("y", 0.5))
    height = float(dimensions.get("z", 0.5))
    return PRIMITIVES[primitive](width, depth, height)


def bounding_size(parts: List[Part]) -> Dict[str, float]:
    """Gabaryt calej bryly - do sprawdzenia, czy generator nie wyszedl poza katalog."""
    if not parts:
        return {"x": 0.0, "y": 0.0, "z": 0.0}
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for part in parts:
        for axis in range(3):
            half = part["size_m"][axis] / 2.0
            lo[axis] = min(lo[axis], part["center_m"][axis] - half)
            hi[axis] = max(hi[axis], part["center_m"][axis] + half)
    return {"x": hi[0] - lo[0], "y": hi[1] - lo[1], "z": hi[2] - lo[2]}
