"""Testy regul walidacji sceny.

Kazdy test buduje minimalna poprawna scene i psuje w niej jedna rzecz,
zeby bylo widac, ktora regula zareagowala.
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from roomlib import validate  # noqa: E402

VALID_SCENE = {
    "schema_version": "0.1",
    "scene_id": "test-room-001",
    "units": "m",
    "coordinate_system": "right_handed_z_up",
    "status": "draft",
    "sources": [{"kind": "floor_plan", "file": "rzut.pdf", "note": "wymiar referencyjny 5.00 m"}],
    "rooms": [
        {
            "id": "living-room",
            "polygon_xy_m": [[0, 0], [5, 0], [5, 4], [0, 4]],
            "height_m": 2.7,
            "openings": [
                {"kind": "door", "wall_index": 0, "offset_m": 0.5, "width_m": 0.9, "sill_m": 0, "height_m": 2.1}
            ],
            "evidence": "Wymiary z rzutu architektonicznego, skala potwierdzona.",
            "review_notes": "",
        }
    ],
    "furniture": [],
    "variants": [],
}

CATALOG = {
    "sofa-001": {
        "product_id": "sofa-001",
        "license": "commercial-use-granted",
        "dimensions_m": {"x": 2.0, "y": 0.9, "z": 0.8},
        "model_path": "catalog/models/sofa-001.glb",
    },
    "table-001": {
        "product_id": "table-001",
        "license": "commercial-use-granted",
        "dimensions_m": {"x": 1.2, "y": 0.8, "z": 0.75},
        "model_path": "catalog/models/table-001.glb",
    },
}


def scene(**overrides):
    data = copy.deepcopy(VALID_SCENE)
    data.update(copy.deepcopy(overrides))
    return data


def check(data, catalog=None):
    return validate.validate_scene(data, catalog=catalog or {}, check_models=False)


class TestValidScene(unittest.TestCase):
    def test_baseline_has_no_errors(self):
        report = check(scene())
        self.assertTrue(report.ok, report.codes())

    def test_baseline_has_no_warnings(self):
        report = check(scene())
        self.assertEqual(report.warnings, [], report.codes())


class TestHeader(unittest.TestCase):
    def test_missing_schema_version(self):
        data = scene()
        del data["schema_version"]
        self.assertIn("header.schema_version.missing", check(data).codes())

    def test_unsupported_schema_version(self):
        self.assertIn("header.schema_version.unsupported", check(scene(schema_version="9.9")).codes())

    def test_wrong_units_are_rejected(self):
        self.assertIn("header.units", check(scene(units="cm")).codes())

    def test_wrong_coordinate_system_is_rejected(self):
        self.assertIn("header.coordinate_system", check(scene(coordinate_system="y_up")).codes())

    def test_unknown_status_is_rejected(self):
        self.assertIn("header.status", check(scene(status="gotowe")).codes())

    def test_scene_id_with_slash_is_rejected(self):
        self.assertIn("header.scene_id.charset", check(scene(scene_id="a/b")).codes())

    def test_empty_sources_warn_on_draft(self):
        report = check(scene(sources=[]))
        self.assertIn("header.sources.empty", report.codes())
        self.assertTrue(report.ok)

    def test_empty_sources_are_error_when_approved(self):
        report = check(scene(sources=[], status="approved"))
        self.assertIn("header.sources.empty_when_approved", report.codes())
        self.assertFalse(report.ok)


class TestRooms(unittest.TestCase):
    def test_scene_without_rooms_is_rejected(self):
        self.assertIn("scene.rooms.empty", check(scene(rooms=[])).codes())

    def test_duplicate_room_ids(self):
        data = scene()
        data["rooms"].append(copy.deepcopy(data["rooms"][0]))
        self.assertIn("room.id.duplicate", check(data).codes())

    def test_negative_height_is_rejected(self):
        data = scene()
        data["rooms"][0]["height_m"] = -2.7
        self.assertIn("room.height.invalid", check(data).codes())

    def test_unusual_height_only_warns(self):
        data = scene()
        data["rooms"][0]["height_m"] = 8.0
        report = check(data)
        self.assertIn("room.height.unusual", report.codes())
        self.assertTrue(report.ok)

    def test_self_intersecting_polygon(self):
        data = scene()
        data["rooms"][0]["polygon_xy_m"] = [[0, 0], [5, 0], [0, 4], [5, 4]]
        self.assertIn("room.polygon.self_intersection", check(data).codes())

    def test_polygon_with_two_points(self):
        data = scene()
        data["rooms"][0]["polygon_xy_m"] = [[0, 0], [5, 0]]
        self.assertIn("room.polygon.too_few_points", check(data).codes())

    def test_polygon_with_text_coordinate(self):
        data = scene()
        data["rooms"][0]["polygon_xy_m"] = [[0, 0], ["5", 0], [5, 4], [0, 4]]
        self.assertIn("room.polygon.bad_point", check(data).codes())

    def test_centimetres_mistaken_for_metres_are_flagged(self):
        data = scene()
        data["rooms"][0]["polygon_xy_m"] = [[0, 0], [500, 0], [500, 400], [0, 400]]
        self.assertIn("room.polygon.huge", check(data).codes())

    def test_missing_evidence_warns(self):
        data = scene()
        data["rooms"][0]["evidence"] = ""
        report = check(data)
        self.assertIn("room.evidence.missing", report.codes())
        self.assertTrue(report.ok)


class TestExpectedArea(unittest.TestCase):
    """Kontrola powierzchni: liczba z dokumentacji kontra wielokat.

    Pokoj bazowy to prostokat 5 x 4 m, czyli 20,00 m2.
    """

    def _with_expected(self, value):
        data = scene()
        data["rooms"][0]["expected_area_m2"] = value
        return data

    def test_matching_area_passes_clean(self):
        report = check(self._with_expected(20.0))
        self.assertTrue(report.ok, report.codes())
        self.assertEqual(report.warnings, [], report.codes())

    def test_absent_field_is_not_an_error(self):
        report = check(scene())
        self.assertNotIn("room.expected_area.mismatch", report.codes())
        self.assertNotIn("room.expected_area.drift", report.codes())

    def test_rounding_difference_is_tolerated(self):
        # 3 cm2 roznicy - ponizej progu bezwzglednego, cisza.
        report = check(self._with_expected(20.03))
        self.assertNotIn("room.expected_area.drift", report.codes())
        self.assertTrue(report.ok)

    def test_small_drift_only_warns(self):
        # 2 % roznicy: miedzy progiem ostrzezenia a progiem bledu.
        report = check(self._with_expected(20.4))
        self.assertIn("room.expected_area.drift", report.codes())
        self.assertTrue(report.ok)

    def test_metre_sized_mistake_in_a_draft_only_warns(self):
        # Szkic wolno miec niedokonczony - generator ma go zbudowac,
        # zeby bylo co ogladac i poprawiac.
        report = check(self._with_expected(25.0))
        self.assertIn("room.expected_area.mismatch", report.codes())
        self.assertTrue(report.ok)

    def test_metre_sized_mistake_blocks_an_approved_scene(self):
        data = self._with_expected(25.0)
        data["status"] = "approved"
        report = check(data)
        self.assertIn("room.expected_area.mismatch", report.codes())
        self.assertFalse(report.ok)

    def test_approved_scene_with_matching_area_passes(self):
        data = self._with_expected(20.0)
        data["status"] = "approved"
        report = check(data)
        self.assertTrue(report.ok, report.codes())

    def test_error_message_states_both_numbers(self):
        report = check(self._with_expected(25.0))
        issue = [i for i in report.issues if i.code == "room.expected_area.mismatch"][0]
        self.assertIn("20.00", issue.message)
        self.assertIn("25.00", issue.message)

    def test_negative_expected_area_is_rejected(self):
        self.assertIn("room.expected_area.invalid", check(self._with_expected(-5.0)).codes())

    def test_text_expected_area_is_rejected(self):
        self.assertIn("room.expected_area.invalid", check(self._with_expected("20")).codes())

    def test_tiny_room_uses_absolute_floor_not_percentage(self):
        # 0,04 m2 roznicy to duzy procent malego pomieszczenia,
        # ale wciaz mniej niz prog bezwzgledny - nie zglaszamy.
        data = scene()
        data["rooms"][0]["polygon_xy_m"] = [[0, 0], [1.2, 0], [1.2, 1], [0, 1]]
        data["rooms"][0]["openings"] = []
        data["rooms"][0]["expected_area_m2"] = 1.24
        report = check(data)
        self.assertNotIn("room.expected_area.mismatch", report.codes())
        self.assertNotIn("room.expected_area.drift", report.codes())

    def test_approved_scene_is_blocked_by_area_drift(self):
        data = self._with_expected(20.4)
        data["status"] = "approved"
        report = check(data)
        self.assertFalse(report.ok)
        self.assertIn("scene.approved_with_warnings", report.codes())


class TestOpenings(unittest.TestCase):
    def _with_opening(self, **fields):
        data = scene()
        opening = data["rooms"][0]["openings"][0]
        opening.update(fields)
        return data

    def test_wall_index_out_of_range(self):
        self.assertIn("opening.wall_index.range", check(self._with_opening(wall_index=9)).codes())

    def test_negative_wall_index(self):
        self.assertIn("opening.wall_index.range", check(self._with_opening(wall_index=-1)).codes())

    def test_opening_wider_than_wall(self):
        self.assertIn("opening.exceeds_wall", check(self._with_opening(width_m=9.0)).codes())

    def test_opening_pushed_past_wall_end(self):
        self.assertIn("opening.exceeds_wall", check(self._with_opening(offset_m=4.5, width_m=0.9)).codes())

    def test_opening_exactly_filling_wall_is_allowed(self):
        report = check(self._with_opening(offset_m=0.0, width_m=5.0))
        self.assertTrue(report.ok, report.codes())

    def test_opening_taller_than_room(self):
        self.assertIn(
            "opening.exceeds_room_height", check(self._with_opening(sill_m=1.0, height_m=2.1)).codes()
        )

    def test_unknown_opening_kind(self):
        self.assertIn("opening.kind", check(self._with_opening(kind="brama")).codes())

    def test_window_at_floor_level_warns(self):
        report = check(self._with_opening(kind="window", sill_m=0.0))
        self.assertIn("opening.window.floor_level", report.codes())

    def test_door_with_raised_sill_warns(self):
        report = check(self._with_opening(sill_m=0.4))
        self.assertIn("opening.door.raised_sill", report.codes())

    def test_overlapping_openings_on_same_wall(self):
        data = scene()
        data["rooms"][0]["openings"].append(
            {"kind": "window", "wall_index": 0, "offset_m": 1.0, "width_m": 1.2, "sill_m": 0.9, "height_m": 1.2}
        )
        self.assertIn("opening.overlap", check(data).codes())

    def test_adjacent_openings_touching_are_allowed(self):
        data = scene()
        data["rooms"][0]["openings"].append(
            {"kind": "window", "wall_index": 0, "offset_m": 1.4, "width_m": 1.2, "sill_m": 0.9, "height_m": 1.2}
        )
        report = check(data)
        self.assertNotIn("opening.overlap", report.codes())

    def test_openings_on_different_walls_do_not_collide(self):
        data = scene()
        data["rooms"][0]["openings"].append(
            {"kind": "window", "wall_index": 1, "offset_m": 0.5, "width_m": 1.2, "sill_m": 0.9, "height_m": 1.2}
        )
        report = check(data)
        self.assertNotIn("opening.overlap", report.codes())


class TestFurniture(unittest.TestCase):
    def _with_furniture(self, *items):
        data = scene()
        data["furniture"] = list(items)
        return data

    def test_unknown_product_is_rejected(self):
        data = self._with_furniture(
            {"id": "f1", "product_id": "brak-takiego", "position_m": [2, 2, 0], "rotation_deg": 0}
        )
        self.assertIn("furniture.product_id.unknown", check(data, CATALOG).codes())

    def test_product_without_licence_is_rejected(self):
        catalog = copy.deepcopy(CATALOG)
        catalog["sofa-001"]["license"] = ""
        data = self._with_furniture(
            {"id": "f1", "product_id": "sofa-001", "position_m": [2, 2, 0], "rotation_deg": 0}
        )
        self.assertIn("product.license.missing", check(data, catalog).codes())

    def test_furniture_outside_room_is_rejected(self):
        data = self._with_furniture(
            {
                "id": "f1",
                "product_id": "sofa-001",
                "room_id": "living-room",
                "position_m": [20, 20, 0],
                "rotation_deg": 0,
            }
        )
        self.assertIn("furniture.outside_room", check(data, CATALOG).codes())

    def test_furniture_in_unknown_room(self):
        data = self._with_furniture(
            {
                "id": "f1",
                "product_id": "sofa-001",
                "room_id": "kuchnia",
                "position_m": [2, 2, 0],
                "rotation_deg": 0,
            }
        )
        self.assertIn("furniture.room_id.unknown", check(data, CATALOG).codes())

    def test_duplicate_furniture_ids(self):
        item = {
            "id": "f1",
            "product_id": "sofa-001",
            "room_id": "living-room",
            "position_m": [1, 1, 0],
            "rotation_deg": 0,
        }
        second = copy.deepcopy(item)
        second["position_m"] = [4, 3, 0]
        self.assertIn("furniture.id.duplicate", check(self._with_furniture(item, second), CATALOG).codes())

    def test_intersecting_furniture_warns(self):
        first = {
            "id": "sofa",
            "product_id": "sofa-001",
            "room_id": "living-room",
            "position_m": [2.0, 2.0, 0],
            "rotation_deg": 0,
        }
        second = {
            "id": "stol",
            "product_id": "table-001",
            "room_id": "living-room",
            "position_m": [2.3, 2.0, 0],
            "rotation_deg": 0,
        }
        report = check(self._with_furniture(first, second), CATALOG)
        self.assertIn("furniture.overlap", report.codes())
        self.assertTrue(report.ok)

    def test_separated_furniture_does_not_warn(self):
        first = {
            "id": "sofa",
            "product_id": "sofa-001",
            "room_id": "living-room",
            "position_m": [1.5, 1.0, 0],
            "rotation_deg": 0,
        }
        second = {
            "id": "stol",
            "product_id": "table-001",
            "room_id": "living-room",
            "position_m": [1.5, 3.0, 0],
            "rotation_deg": 0,
        }
        report = check(self._with_furniture(first, second), CATALOG)
        self.assertNotIn("furniture.overlap", report.codes())

    def test_position_with_two_coordinates_is_rejected(self):
        data = self._with_furniture({"id": "f1", "product_id": "sofa-001", "position_m": [2, 2]})
        self.assertIn("furniture.position.invalid", check(data, CATALOG).codes())


class TestVariants(unittest.TestCase):
    def _base(self):
        data = scene()
        data["furniture"] = [
            {
                "id": "sofa",
                "product_id": "sofa-001",
                "room_id": "living-room",
                "position_m": [2.0, 2.0, 0],
                "rotation_deg": 0,
            }
        ]
        return data

    def test_substitution_of_unknown_furniture(self):
        data = self._base()
        data["variants"] = [
            {"id": "v1", "substitutions": [{"furniture_id": "fotel", "product_id": "table-001"}]}
        ]
        self.assertIn("variant.substitution.unknown_furniture", check(data, CATALOG).codes())

    def test_substitution_with_unknown_product(self):
        data = self._base()
        data["variants"] = [
            {"id": "v1", "substitutions": [{"furniture_id": "sofa", "product_id": "brak"}]}
        ]
        self.assertIn("variant.substitution.unknown_product", check(data, CATALOG).codes())

    def test_duplicate_variant_ids(self):
        data = self._base()
        data["variants"] = [{"id": "v1", "substitutions": []}, {"id": "v1", "substitutions": []}]
        self.assertIn("variant.id.duplicate", check(data, CATALOG).codes())

    def test_single_variant_is_only_an_observation(self):
        data = self._base()
        data["variants"] = [{"id": "v1", "substitutions": []}]
        report = check(data, CATALOG)
        self.assertIn("scene.variants.single", report.codes())
        self.assertTrue(report.ok)

    def test_two_valid_variants_pass(self):
        data = self._base()
        data["variants"] = [
            {"id": "nordic", "substitutions": [{"furniture_id": "sofa", "product_id": "table-001"}]},
            {"id": "warm", "substitutions": []},
        ]
        report = check(data, CATALOG)
        self.assertTrue(report.ok, report.codes())


class TestApprovalGate(unittest.TestCase):
    def test_approved_scene_with_warning_is_blocked(self):
        data = scene(status="approved")
        data["rooms"][0]["evidence"] = ""
        report = validate.validate_scene(data, catalog={}, check_models=False)
        self.assertIn("scene.approved_with_warnings", report.codes())
        self.assertFalse(report.ok)

    def test_clean_approved_scene_is_buildable(self):
        data = scene(status="approved")
        report = validate.validate_scene(data, catalog={}, check_models=False)
        self.assertTrue(report.ok, report.codes())
        self.assertTrue(validate.is_buildable(data, report))

    def test_draft_scene_is_not_buildable_even_when_clean(self):
        data = scene(status="draft")
        report = validate.validate_scene(data, catalog={}, check_models=False)
        self.assertTrue(report.ok)
        self.assertFalse(validate.is_buildable(data, report))

    def test_example_scene_is_never_buildable(self):
        data = scene(status="example_only")
        report = validate.validate_scene(data, catalog={}, check_models=False)
        self.assertFalse(validate.is_buildable(data, report))


if __name__ == "__main__":
    unittest.main()
