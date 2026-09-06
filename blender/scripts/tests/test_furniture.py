"""Testy brył meblowych - wymiary i wysokosci uzytkowe, nie wyglad."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from roomlib import furniture as f  # noqa: E402


def extent(parts, axis):
    lo = min(p["center_m"][axis] - p["size_m"][axis] / 2 for p in parts)
    hi = max(p["center_m"][axis] + p["size_m"][axis] / 2 for p in parts)
    return lo, hi


class TestAllPrimitives(unittest.TestCase):
    DIMS = {"x": 1.2, "y": 0.7, "z": 0.85}

    def test_every_primitive_builds(self):
        for name in f.PRIMITIVES:
            self.assertTrue(f.build(name, self.DIMS), name)

    def test_unknown_primitive_raises(self):
        with self.assertRaises(KeyError):
            f.build("helikopter", self.DIMS)

    def test_nothing_sinks_below_the_floor(self):
        for name in f.PRIMITIVES:
            parts = f.build(name, self.DIMS)
            lo, _ = extent(parts, 2)
            self.assertGreaterEqual(round(lo, 6), 0.0, name)

    def test_every_part_has_positive_size(self):
        for name in f.PRIMITIVES:
            for part in f.build(name, self.DIMS):
                for size in part["size_m"]:
                    self.assertGreater(size, 0.0, "{} / {}".format(name, part["name"]))

    def test_every_part_has_a_known_role(self):
        for name in f.PRIMITIVES:
            for part in f.build(name, self.DIMS):
                self.assertIn(part["role"], f.FURNITURE_ROLES, name)

    def test_footprint_matches_the_catalogue(self):
        # Rzut mebla musi zgadzac sie z gabarytem z katalogu, bo na nim
        # walidator wykrywa przenikajace sie meble.
        for name in f.PRIMITIVES:
            if name in ("counter", "shower"):
                continue  # blat i kabina celowo wystaja poza korpus
            size = f.bounding_size(f.build(name, self.DIMS))
            self.assertAlmostEqual(size["x"], self.DIMS["x"], places=2, msg=name)
            self.assertAlmostEqual(size["y"], self.DIMS["y"], places=2, msg=name)

    def test_only_the_kitchen_run_grows_above_its_catalogue_height(self):
        for name in f.PRIMITIVES:
            size = f.bounding_size(f.build(name, self.DIMS))
            if name == "kitchen_run":
                self.assertGreater(size["z"], self.DIMS["z"])  # szafki gorne
            else:
                self.assertLessEqual(round(size["z"], 3), round(self.DIMS["z"] + 0.05, 3), name)

    def test_result_is_deterministic(self):
        for name in f.PRIMITIVES:
            self.assertEqual(f.build(name, self.DIMS), f.build(name, self.DIMS), name)


class TestSofa(unittest.TestCase):
    def setUp(self):
        self.parts = f.build("sofa", {"x": 2.10, "y": 0.95, "z": 0.82})

    def test_seat_cushions_sit_at_a_usable_height(self):
        cushions = [p for p in self.parts if p["name"].startswith("cushion")]
        self.assertTrue(cushions)
        for cushion in cushions:
            self.assertTrue(0.32 <= cushion["center_m"][2] <= 0.52, cushion["center_m"])

    def test_wide_sofa_gets_more_cushions_than_a_narrow_one(self):
        narrow = f.build("sofa", {"x": 1.4, "y": 0.9, "z": 0.8})
        wide = f.build("sofa", {"x": 2.6, "y": 0.9, "z": 0.8})
        count = lambda parts: len([p for p in parts if p["name"].startswith("cushion")])  # noqa: E731
        self.assertGreater(count(wide), count(narrow))

    def test_upholstery_dominates_the_material_roles(self):
        soft = [p for p in self.parts if p["role"] == f.SOFT]
        self.assertGreater(len(soft), len(self.parts) / 2)

    def test_back_is_at_the_rear(self):
        back = [p for p in self.parts if p["name"] == "back"][0]
        self.assertGreater(back["center_m"][1], 0.0)


class TestBed(unittest.TestCase):
    def setUp(self):
        self.parts = f.build("bed", {"x": 1.60, "y": 2.00, "z": 0.95})

    def test_mattress_lies_on_the_frame(self):
        frame = [p for p in self.parts if p["name"] == "frame"][0]
        mattress = [p for p in self.parts if p["name"] == "mattress"][0]
        frame_top = frame["center_m"][2] + frame["size_m"][2] / 2
        mattress_bottom = mattress["center_m"][2] - mattress["size_m"][2] / 2
        self.assertAlmostEqual(frame_top, mattress_bottom, places=6)

    def test_two_pillows_at_the_headboard(self):
        pillows = [p for p in self.parts if p["name"].startswith("pillow")]
        self.assertEqual(len(pillows), 2)
        for pillow in pillows:
            self.assertGreater(pillow["center_m"][1], 0.0)

    def test_pillows_do_not_overlap_each_other(self):
        left, right = [p for p in self.parts if p["name"].startswith("pillow")]
        gap = abs(left["center_m"][0] - right["center_m"][0])
        self.assertGreaterEqual(gap, (left["size_m"][0] + right["size_m"][0]) / 2)


class TestKitchenAndBathroom(unittest.TestCase):
    def test_worktop_lands_at_a_working_height(self):
        parts = f.build("kitchen_run", {"x": 3.0, "y": 0.60, "z": 0.90})
        worktop = [p for p in parts if p["name"] == "worktop"][0]
        top = worktop["center_m"][2] + worktop["size_m"][2] / 2
        self.assertTrue(0.85 <= top <= 0.95, top)

    def test_upper_cabinets_leave_room_above_the_worktop(self):
        parts = f.build("kitchen_run", {"x": 3.0, "y": 0.60, "z": 0.90})
        worktop = [p for p in parts if p["name"] == "worktop"][0]
        upper = [p for p in parts if p["name"] == "upper"][0]
        clearance = (upper["center_m"][2] - upper["size_m"][2] / 2) - (
            worktop["center_m"][2] + worktop["size_m"][2] / 2
        )
        self.assertGreaterEqual(clearance, 0.45)

    def test_kitchen_fronts_scale_with_width(self):
        narrow = f.build("kitchen_run", {"x": 1.2, "y": 0.6, "z": 0.9})
        wide = f.build("kitchen_run", {"x": 3.6, "y": 0.6, "z": 0.9})
        count = lambda parts: len([p for p in parts if p["name"].startswith("front")])  # noqa: E731
        self.assertGreater(count(wide), count(narrow))

    def test_wc_has_a_bowl_and_a_cistern(self):
        names = {p["name"] for p in f.build("wc", {"x": 0.38, "y": 0.68, "z": 0.78})}
        self.assertEqual(names, {"bowl", "cistern"})

    def test_basin_bowl_sits_on_top_of_the_cabinet(self):
        parts = f.build("basin", {"x": 0.80, "y": 0.48, "z": 0.85})
        cabinet = [p for p in parts if p["name"] == "cabinet"][0]
        bowl = [p for p in parts if p["name"] == "bowl"][0]
        self.assertGreater(bowl["center_m"][2], cabinet["center_m"][2])

    def test_rug_is_almost_flat(self):
        parts = f.build("rug", {"x": 2.4, "y": 1.7, "z": 0.02})
        self.assertLess(parts[0]["size_m"][2], 0.03)


class TestBoundingSize(unittest.TestCase):
    def test_empty_list_gives_zeros(self):
        self.assertEqual(f.bounding_size([]), {"x": 0.0, "y": 0.0, "z": 0.0})

    def test_single_part_returns_its_size(self):
        parts = f.build("rug", {"x": 2.0, "y": 1.0, "z": 0.02})
        size = f.bounding_size(parts)
        self.assertAlmostEqual(size["x"], 2.0, places=3)


if __name__ == "__main__":
    unittest.main()
