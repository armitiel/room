"""Testy planu budowy - wymiary sprawdzane liczbowo, bez uruchamiania Blendera."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from roomlib import build_plan as bp  # noqa: E402
from roomlib import geometry as geo  # noqa: E402

SQUARE = [(0.0, 0.0), (5.0, 0.0), (5.0, 4.0), (0.0, 4.0)]
L_SHAPE = [(0, 0), (6, 0), (6, 3), (3, 3), (3, 5), (0, 5)]
THICKNESS = 0.12

DOOR = {"kind": "door", "wall_index": 0, "offset_m": 0.5, "width_m": 0.9, "sill_m": 0.0, "height_m": 2.1}
WINDOW = {"kind": "window", "wall_index": 1, "offset_m": 1.0, "width_m": 1.4, "sill_m": 0.9, "height_m": 1.4}


def room(polygon=None, openings=None, height=2.7):
    return {
        "id": "living-room",
        "polygon_xy_m": [list(p) for p in (polygon or SQUARE)],
        "height_m": height,
        "openings": openings if openings is not None else [dict(DOOR)],
    }


class TestOffsetPolygon(unittest.TestCase):
    def test_offset_grows_the_footprint_by_thickness_on_every_side(self):
        outer = bp.offset_polygon(SQUARE, THICKNESS)
        min_x, min_y, max_x, max_y = geo.bounding_box(outer)
        self.assertAlmostEqual(min_x, -THICKNESS, places=9)
        self.assertAlmostEqual(min_y, -THICKNESS, places=9)
        self.assertAlmostEqual(max_x, 5.0 + THICKNESS, places=9)
        self.assertAlmostEqual(max_y, 4.0 + THICKNESS, places=9)

    def test_outer_area_matches_hand_calculation(self):
        outer = bp.offset_polygon(SQUARE, THICKNESS)
        self.assertAlmostEqual(geo.area(outer), 5.24 * 4.24, places=9)

    def test_reflex_corner_is_offset_outward_not_inward(self):
        # W ksztalcie L wierzcholek (3, 3) jest naroznikiem wklestym.
        outer = bp.offset_polygon(L_SHAPE, THICKNESS)
        self.assertAlmostEqual(outer[3][0], 3.0 + THICKNESS, places=9)
        self.assertAlmostEqual(outer[3][1], 3.0 + THICKNESS, places=9)

    def test_offset_polygon_stays_simple(self):
        self.assertTrue(geo.is_simple(bp.offset_polygon(L_SHAPE, THICKNESS)))

    def test_offset_encloses_the_original(self):
        outer = bp.offset_polygon(SQUARE, THICKNESS)
        for point in SQUARE:
            self.assertTrue(geo.point_in_polygon(outer, point))


class TestWalls(unittest.TestCase):
    def test_one_wall_per_edge(self):
        plan = bp.plan_room(room(), THICKNESS)
        self.assertEqual(len(plan["walls"]), 4)

    def test_inner_lengths_match_the_floor_plan(self):
        plan = bp.plan_room(room(), THICKNESS)
        self.assertEqual([round(w["length_m"], 6) for w in plan["walls"]], [5.0, 4.0, 5.0, 4.0])

    def test_each_wall_base_is_a_quad(self):
        plan = bp.plan_room(room(), THICKNESS)
        for wall in plan["walls"]:
            self.assertEqual(len(wall["base"]), 4)

    def test_adjacent_walls_share_their_corner_points(self):
        plan = bp.plan_room(room(), THICKNESS)
        walls = plan["walls"]
        for index, wall in enumerate(walls):
            nxt = walls[(index + 1) % len(walls)]
            # inner_end sciany i musi byc inner_start sciany i+1
            self.assertAlmostEqual(wall["inner_end"][0], nxt["inner_start"][0], places=9)
            self.assertAlmostEqual(wall["inner_end"][1], nxt["inner_start"][1], places=9)
            # to samo dla lica zewnetrznego: base[2] sciany i == base[3] sciany i+1
            self.assertAlmostEqual(wall["base"][2][0], nxt["base"][3][0], places=9)
            self.assertAlmostEqual(wall["base"][2][1], nxt["base"][3][1], places=9)

    def test_floor_area_uses_inner_face(self):
        plan = bp.plan_room(room(), THICKNESS)
        self.assertAlmostEqual(plan["floor_area_m2"], 20.0, places=9)

    def test_clockwise_input_is_normalised_but_wall_index_is_preserved(self):
        clockwise = room(polygon=SQUARE[::-1])
        # W zapisie odwroconym sciana 0 biegnie z (0,4) do (5,4) i tez ma 5 m.
        plan = bp.plan_room(clockwise, THICKNESS)
        source_zero = [w for w in plan["walls"] if w["source_wall_index"] == 0][0]
        self.assertAlmostEqual(source_zero["length_m"], 5.0, places=9)
        self.assertAlmostEqual(plan["floor_area_m2"], 20.0, places=9)


class TestClockwiseInput(unittest.TestCase):
    """Rzut zapisany zgodnie z ruchem wskazowek zegara musi dac te sama bryle.

    Generator normalizuje kolejnosc wierzcholkow, ale offset_m otworu liczy
    sie od poczatku sciany tak, jak zapisano ja w pliku. Bez odbicia tej
    odleglosci drzwi wyladowalyby po przeciwnej stronie sciany.
    """

    def _cut_for(self, polygon, wall_index):
        opening = dict(DOOR, wall_index=wall_index)
        plan = bp.plan_room(room(polygon=polygon, openings=[opening]), THICKNESS)
        return plan["openings"][0]

    def test_door_stays_on_the_same_physical_wall(self):
        # Sciana 0 zapisu CCW to (0,0)->(5,0). W zapisie odwroconym ta sama
        # krawedz jest sciana 2, przebiegana od (5,0) do (0,0). Otwor musi
        # wyladowac w tej samej scianie i na tej samej wysokosci.
        ccw = self._cut_for(SQUARE, 0)
        clockwise = self._cut_for(SQUARE[::-1], 2)
        self.assertAlmostEqual(ccw["center_m"][1], clockwise["center_m"][1], places=9)
        self.assertAlmostEqual(ccw["center_m"][2], clockwise["center_m"][2], places=9)

    def test_door_is_mirrored_because_the_wall_starts_at_the_other_end(self):
        # To nie jest ten sam otwor: offset_m liczy sie od poczatku sciany,
        # a ten w obu zapisach lezy po przeciwnych stronach. Suma odlegloscii
        # od obu koncow musi dac dlugosc sciany.
        ccw = self._cut_for(SQUARE, 0)
        clockwise = self._cut_for(SQUARE[::-1], 2)
        self.assertAlmostEqual(ccw["center_m"][0] + clockwise["center_m"][0], 5.0, places=9)

    def test_offset_is_measured_from_the_wall_start_as_written(self):
        # W zapisie odwroconym sciana 2 zaczyna sie w (5,0), wiec drzwi
        # z offset_m=0.5 maja srodek na x = 5 - 0.95 = 4.05.
        cut = self._cut_for(SQUARE[::-1], 2)
        self.assertAlmostEqual(cut["center_m"][0], 4.05, places=9)

    def test_wall_count_and_area_survive_normalisation(self):
        plan = bp.plan_room(room(polygon=SQUARE[::-1], openings=[]), THICKNESS)
        self.assertEqual(len(plan["walls"]), 4)
        self.assertAlmostEqual(plan["floor_area_m2"], 20.0, places=9)

    def test_every_source_wall_index_is_used_exactly_once(self):
        plan = bp.plan_room(room(polygon=L_SHAPE[::-1], openings=[]), THICKNESS)
        indices = sorted(w["source_wall_index"] for w in plan["walls"])
        self.assertEqual(indices, list(range(len(L_SHAPE))))

    def test_source_wall_lengths_match_the_file_order(self):
        polygon = L_SHAPE[::-1]
        expected = geo.wall_lengths(polygon)
        plan = bp.plan_room(room(polygon=polygon, openings=[]), THICKNESS)
        for wall in plan["walls"]:
            self.assertAlmostEqual(
                wall["length_m"], expected[wall["source_wall_index"]], places=9
            )


class TestOpeningCuts(unittest.TestCase):
    def test_door_cut_is_centred_on_the_opening(self):
        plan = bp.plan_room(room(), THICKNESS)
        cut = plan["openings"][0]
        self.assertAlmostEqual(cut["center_m"][0], 0.95, places=9)
        self.assertAlmostEqual(cut["center_m"][2], 1.05, places=9)

    def test_cut_is_thicker_than_the_wall_so_the_boolean_is_clean(self):
        plan = bp.plan_room(room(), THICKNESS)
        cut = plan["openings"][0]
        self.assertGreater(cut["size_m"][1], THICKNESS)

    def test_cut_width_and_height_match_the_contract(self):
        plan = bp.plan_room(room(), THICKNESS)
        cut = plan["openings"][0]
        self.assertAlmostEqual(cut["size_m"][0], 0.9, places=9)
        self.assertAlmostEqual(cut["size_m"][2], 2.1, places=9)

    def test_cut_sits_inside_the_wall_thickness(self):
        plan = bp.plan_room(room(), THICKNESS)
        cut = plan["openings"][0]
        # Sciana 0 rozciaga sie od y=0 do y=-0.12, wiec srodek wypada na -0.06.
        self.assertAlmostEqual(cut["center_m"][1], -THICKNESS / 2.0, places=9)

    def test_window_on_second_wall_is_rotated_with_it(self):
        plan = bp.plan_room(room(openings=[dict(WINDOW)]), THICKNESS)
        cut = plan["openings"][0]
        self.assertAlmostEqual(abs(cut["rotation_deg"]), 90.0, places=6)

    def test_window_cut_is_lifted_to_the_sill(self):
        plan = bp.plan_room(room(openings=[dict(WINDOW)]), THICKNESS)
        cut = plan["openings"][0]
        self.assertAlmostEqual(cut["center_m"][2], 0.9 + 1.4 / 2.0, places=9)

    def test_cut_centre_lies_within_the_room_extents(self):
        plan = bp.plan_room(room(openings=[dict(DOOR), dict(WINDOW)]), THICKNESS)
        for cut in plan["openings"]:
            x, y, z = cut["center_m"]
            self.assertTrue(-1.0 <= x <= 6.0)
            self.assertTrue(-1.0 <= y <= 5.0)
            self.assertTrue(0.0 < z < 2.7)

    def test_unknown_wall_index_raises(self):
        bad = room(openings=[dict(DOOR, wall_index=17)])
        with self.assertRaises(bp.BuildPlanError):
            bp.plan_room(bad, THICKNESS)


class TestScenePlan(unittest.TestCase):
    def _scene(self):
        return {
            "scene_id": "test-001",
            "status": "approved",
            "rooms": [room(openings=[dict(DOOR), dict(WINDOW)])],
            "furniture": [
                {
                    "id": "sofa",
                    "product_id": "sofa-001",
                    "room_id": "living-room",
                    "position_m": [2.0, 2.0, 0.0],
                    "rotation_deg": 45.0,
                }
            ],
            "variants": [{"id": "nordic", "substitutions": []}],
        }

    def test_totals_are_counted(self):
        plan = bp.plan_scene(self._scene(), {"sofa-001": {"model_path": "a.glb"}}, THICKNESS)
        self.assertEqual(plan["totals"]["rooms"], 1)
        self.assertEqual(plan["totals"]["walls"], 4)
        self.assertEqual(plan["totals"]["openings"], 2)
        self.assertEqual(plan["totals"]["furniture"], 1)
        self.assertAlmostEqual(plan["totals"]["floor_area_m2"], 20.0)

    def test_furniture_carries_the_model_path_from_the_catalog(self):
        plan = bp.plan_scene(self._scene(), {"sofa-001": {"model_path": "catalog/models/sofa.glb"}}, THICKNESS)
        self.assertEqual(plan["furniture"][0]["model_path"], "catalog/models/sofa.glb")

    def test_missing_product_leaves_the_model_path_empty_instead_of_guessing(self):
        plan = bp.plan_scene(self._scene(), {}, THICKNESS)
        self.assertIsNone(plan["furniture"][0]["model_path"])

    def test_plan_is_deterministic(self):
        first = bp.plan_scene(self._scene(), {}, THICKNESS)
        second = bp.plan_scene(self._scene(), {}, THICKNESS)
        self.assertEqual(first, second)

    def test_thickness_is_recorded_in_the_plan(self):
        plan = bp.plan_scene(self._scene(), {}, 0.25)
        self.assertEqual(plan["wall_thickness_m"], 0.25)
        self.assertEqual(plan["rooms"][0]["walls"][0]["thickness_m"], 0.25)


if __name__ == "__main__":
    unittest.main()
