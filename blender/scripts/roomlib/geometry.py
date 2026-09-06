"""Geometria 2D rzutu pomieszczenia.

Czysta matematyka na listach krotek (x, y) w metrach.
Zadnych zaleznosci zewnetrznych - modul dziala tak samo
w CPythonie i w Pythonie Blendera.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

from .constants import EPS_M

Point = Tuple[float, float]
Segment = Tuple[Point, Point]


def signed_area(polygon: Sequence[Point]) -> float:
    """Pole ze znakiem (wzor sznurowadla).

    Dodatnie = wierzcholki w kolejnosci przeciwnej do ruchu wskazowek zegara
    (CCW), co przy ukladzie Z-up oznacza normalna podlogi skierowana w gore.
    """
    total = 0.0
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def area(polygon: Sequence[Point]) -> float:
    """Pole bezwzgledne w m2."""
    return abs(signed_area(polygon))


def is_ccw(polygon: Sequence[Point]) -> bool:
    return signed_area(polygon) > 0.0


def ensure_ccw(polygon: Sequence[Point]) -> List[Point]:
    """Zwraca wielokat w kolejnosci CCW, nie modyfikujac wejscia."""
    pts = list(polygon)
    return pts if is_ccw(pts) else pts[::-1]


def walls(polygon: Sequence[Point]) -> List[Segment]:
    """Sciany jako odcinki. Sciana i laczy wierzcholek i oraz i+1.

    Indeks sciany w scene.json (`wall_index`) odnosi sie do tej listy
    i do KOLEJNOSCI ZAPISANEJ W PLIKU, a nie do wersji po normalizacji.
    """
    n = len(polygon)
    return [(tuple(polygon[i]), tuple(polygon[(i + 1) % n])) for i in range(n)]


def segment_length(seg: Segment) -> float:
    (x1, y1), (x2, y2) = seg
    return math.hypot(x2 - x1, y2 - y1)


def wall_lengths(polygon: Sequence[Point]) -> List[float]:
    return [segment_length(s) for s in walls(polygon)]


def perimeter(polygon: Sequence[Point]) -> float:
    return sum(wall_lengths(polygon))


def point_on_wall(seg: Segment, offset_m: float) -> Point:
    """Punkt na scianie w odleglosci offset_m od jej poczatku."""
    (x1, y1), (x2, y2) = seg
    length = segment_length(seg)
    if length <= EPS_M:
        return (x1, y1)
    t = offset_m / length
    return (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)


def wall_angle_deg(seg: Segment) -> float:
    """Kat sciany wzgledem osi X, w stopniach."""
    (x1, y1), (x2, y2) = seg
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def wall_normal(seg: Segment) -> Point:
    """Jednostkowa normalna sciany, skierowana w lewo od kierunku sciany.

    Dla wielokata CCW lewa strona to wnetrze pomieszczenia.
    """
    (x1, y1), (x2, y2) = seg
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length <= EPS_M:
        return (0.0, 0.0)
    return (-dy / length, dx / length)


def _orientation(a: Point, b: Point, c: Point) -> float:
    """Iloczyn wektorowy (b-a) x (c-a). >0 skret w lewo, <0 w prawo."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, p: Point) -> bool:
    """Czy p lezy na odcinku ab, zakladajac ze jest wspolliniowy."""
    return (
        min(a[0], b[0]) - EPS_M <= p[0] <= max(a[0], b[0]) + EPS_M
        and min(a[1], b[1]) - EPS_M <= p[1] <= max(a[1], b[1]) + EPS_M
    )


def segments_intersect(s1: Segment, s2: Segment) -> bool:
    """Czy dwa odcinki maja punkt wspolny (wlacznie z koncami)."""
    a, b = s1
    c, d = s2
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)

    if (o1 > EPS_M) != (o2 > EPS_M) and (o3 > EPS_M) != (o4 > EPS_M):
        # Ostre przeciecie tylko gdy oba znaki sa istotnie rozne.
        if abs(o1) > EPS_M and abs(o2) > EPS_M and abs(o3) > EPS_M and abs(o4) > EPS_M:
            return True

    if abs(o1) <= EPS_M and _on_segment(a, b, c):
        return True
    if abs(o2) <= EPS_M and _on_segment(a, b, d):
        return True
    if abs(o3) <= EPS_M and _on_segment(c, d, a):
        return True
    if abs(o4) <= EPS_M and _on_segment(c, d, b):
        return True
    return False


def duplicate_vertices(polygon: Sequence[Point]) -> List[int]:
    """Indeksy wierzcholkow pokrywajacych sie z poprzednim (lub domykajacych)."""
    bad = []
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if math.hypot(x2 - x1, y2 - y1) <= EPS_M:
            bad.append(i)
    return bad


def self_intersections(polygon: Sequence[Point]) -> List[Tuple[int, int]]:
    """Pary indeksow scian, ktore sie przecinaja mimo ze nie sasiaduja."""
    segs = walls(polygon)
    n = len(segs)
    hits: List[Tuple[int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            adjacent = (j == i + 1) or (i == 0 and j == n - 1)
            if adjacent:
                continue
            if segments_intersect(segs[i], segs[j]):
                hits.append((i, j))
    return hits


def is_simple(polygon: Sequence[Point]) -> bool:
    """Wielokat prosty: bez powtorzen i bez samoprzeciec."""
    if len(polygon) < 3:
        return False
    if duplicate_vertices(polygon):
        return False
    return not self_intersections(polygon)


def point_in_polygon(polygon: Sequence[Point], p: Point) -> bool:
    """Test parzystosci przeciec (ray casting). Brzeg liczy sie jako wnetrze."""
    x, y = p
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if abs(_orientation((x1, y1), (x2, y2), p)) <= EPS_M and _on_segment(
            (x1, y1), (x2, y2), p
        ):
            return True
        if (y1 > y) != (y2 > y):
            x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x_cross > x:
                inside = not inside
    return inside


def bounding_box(polygon: Sequence[Point]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def footprint_corners(
    center: Point, size_x: float, size_y: float, rotation_deg: float
) -> List[Point]:
    """Naroza prostokatnego rzutu mebla, obroconego wokol wlasnego srodka."""
    rad = math.radians(rotation_deg)
    cos_r, sin_r = math.cos(rad), math.sin(rad)
    hx, hy = size_x / 2.0, size_y / 2.0
    corners = []
    for dx, dy in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
        corners.append(
            (center[0] + dx * cos_r - dy * sin_r, center[1] + dx * sin_r + dy * cos_r)
        )
    return corners


def rects_overlap(a: Sequence[Point], b: Sequence[Point]) -> bool:
    """Kolizja dwoch wypuklych wielokatow metoda osi rozdzielajacej (SAT)."""
    for poly in (a, b):
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            axis = (-(y2 - y1), x2 - x1)
            length = math.hypot(*axis)
            if length <= EPS_M:
                continue
            axis = (axis[0] / length, axis[1] / length)
            proj_a = [p[0] * axis[0] + p[1] * axis[1] for p in a]
            proj_b = [p[0] * axis[0] + p[1] * axis[1] for p in b]
            if max(proj_a) <= min(proj_b) + EPS_M or max(proj_b) <= min(proj_a) + EPS_M:
                return False
    return True


def as_points(raw: Iterable) -> List[Point]:
    """Zamienia liste [[x, y], ...] z JSON na liste krotek."""
    return [(float(p[0]), float(p[1])) for p in raw]
