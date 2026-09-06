"""Testy geometrii rzutu. Uruchomienie: python3 -m unittest discover blender/scripts/tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from roomlib import geometry as geo  # noqa: E402

SQUARE = [(0.0, 0.0), (5.0, 0.0), (5.0, 4.0), (0.0, 4.0)]
L_SHAPE = [(0, 0), (6, 0), (6, 3), (3, 3), (3, 5), (0, 5)]


class TestArea(unittest.TestCase):
    def test_square_area(self):
        self.assertAlmostEqual(geo.area(SQUARE), 20.0)

    def test_l_shape_area(self):
        # 6x3 = 18 plus 3x2 = 6
        self.assertAlmostEqual(geo.area(L_SHAPE), 24.0)

    def test_orientation_is_detected(self):
        self.assertTrue(geo.is_ccw(SQUARE))
        self.assertFalse(geo.is_ccw(SQUARE[::-1]))

    def test_ensure_ccw_does_not_mutate_input(self):
        clockwise = SQUARE[::-1]
        snapshot = list(clockwise)
        fixed = geo.ensure_ccw(clockwise)
        self.assertEqual(clockwise, snapshot)
        self.assertTrue(geo.is_ccw(fixed))


class TestWalls(unittest.TestCase):
    def test_wall_count_matches_vertex_count(self):
        self.assertEqual(len(geo.walls(SQUARE)), len(SQUARE))

    def test_wall_lengths(self):
        self.assertEqual(geo.wall_lengths(SQUARE), [5.0, 4.0, 5.0, 4.0])

    def test_perimeter(self):
        self.assertAlmostEqual(geo.perimeter(SQUARE), 18.0)

    def test_point_on_wall_midpoint(self):
        wall = geo.walls(SQUARE)[0]
        self.assertEqual(geo.point_on_wall(wall, 2.5), (2.5, 0.0))

    def test_normal_of_ccw_polygon_points_inward(self):
        # Sciana 0 biegnie wzdluz osi X; wnetrze lezy w kierunku +Y.
        normal = geo.wall_normal(geo.walls(SQUARE)[0])
        self.assertAlmostEqual(normal[0], 0.0)
        self.assertAlmostEqual(normal[1], 1.0)


class TestSimplicity(unittest.TestCase):
    def test_square_is_simple(self):
        self.assertTrue(geo.is_simple(SQUARE))

    def test_l_shape_is_simple(self):
        self.assertTrue(geo.is_simple(L_SHAPE))

    def test_bowtie_is_not_simple(self):
        bowtie = [(0, 0), (5, 0), (0, 4), (5, 4)]
        self.assertFalse(geo.is_simple(bowtie))
        self.assertEqual(geo.self_intersections(bowtie), [(1, 3)])

    def test_duplicate_vertex_is_caught(self):
        doubled = [(0, 0), (5, 0), (5, 0), (5, 4), (0, 4)]
        self.assertIn(1, geo.duplicate_vertices(doubled))
        self.assertFalse(geo.is_simple(doubled))

    def test_two_points_is_not_simple(self):
        self.assertFalse(geo.is_simple([(0, 0), (1, 1)]))


class TestPointInPolygon(unittest.TestCase):
    def test_inside(self):
        self.assertTrue(geo.point_in_polygon(SQUARE, (2.5, 2.0)))

    def test_outside(self):
        self.assertFalse(geo.point_in_polygon(SQUARE, (7.0, 2.0)))

    def test_on_edge_counts_as_inside(self):
        self.assertTrue(geo.point_in_polygon(SQUARE, (2.5, 0.0)))

    def test_notch_of_l_shape_is_outside(self):
        self.assertFalse(geo.point_in_polygon(L_SHAPE, (5.0, 4.0)))


class TestFootprints(unittest.TestCase):
    def test_unrotated_corners(self):
        corners = geo.footprint_corners((0, 0), 2.0, 1.0, 0.0)
        self.assertIn((-1.0, -0.5), [(round(x, 6), round(y, 6)) for x, y in corners])

    def test_rotation_by_90_swaps_extent(self):
        corners = geo.footprint_corners((0, 0), 2.0, 1.0, 90.0)
        min_x, min_y, max_x, max_y = geo.bounding_box(corners)
        self.assertAlmostEqual(max_x - min_x, 1.0, places=6)
        self.assertAlmostEqual(max_y - min_y, 2.0, places=6)

    def test_overlapping_rectangles(self):
        a = geo.footprint_corners((1, 1), 2.0, 1.0, 0.0)
        b = geo.footprint_corners((1.5, 1), 2.0, 1.0, 0.0)
        self.assertTrue(geo.rects_overlap(a, b))

    def test_separated_rectangles(self):
        a = geo.footprint_corners((1, 1), 2.0, 1.0, 0.0)
        b = geo.footprint_corners((5, 5), 1.0, 1.0, 0.0)
        self.assertFalse(geo.rects_overlap(a, b))

    def test_touching_rectangles_do_not_count_as_overlap(self):
        a = geo.footprint_corners((0, 0), 2.0, 2.0, 0.0)
        b = geo.footprint_corners((2, 0), 2.0, 2.0, 0.0)
        self.assertFalse(geo.rects_overlap(a, b))

    def test_rotation_creates_overlap_that_axis_aligned_check_would_miss(self):
        a = geo.footprint_corners((0, 0), 3.0, 0.5, 45.0)
        b = geo.footprint_corners((0.2, 0.2), 3.0, 0.5, 45.0)
        self.assertTrue(geo.rects_overlap(a, b))


if __name__ == "__main__":
    unittest.main()
