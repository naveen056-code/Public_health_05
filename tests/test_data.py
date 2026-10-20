import datetime as dt
import math
import unittest

from clinic_broker import data


class TestDataModule(unittest.TestCase):
    def test_km_identical_points(self):
        pt = {"latitude": 33.7490, "longitude": -84.3880}
        self.assertAlmostEqual(data._km(pt, pt), 0.0, places=5)

    def test_km_known_distance(self):
        # Atlanta Downtown (33.7490, -84.3880) to Alpharetta (34.0754, -84.2941) is ~37-38 km
        downtown = {"latitude": 33.7490, "longitude": -84.3880}
        alpharetta = {"latitude": 34.0754, "longitude": -84.2941}
        dist = data._km(downtown, alpharetta)
        self.assertGreater(dist, 35.0)
        self.assertLess(dist, 40.0)

    def test_km_clamping_domain_error(self):
        # Coordinates at extreme poles / antipodal where un-clamped math could result in x > 1.0
        north_pole = {"latitude": 90.0, "longitude": 0.0}
        south_pole = {"latitude": -90.0, "longitude": 0.0}
        dist = data._km(north_pole, south_pole)
        self.assertAlmostEqual(dist, math.pi * 6371, places=1)

    def test_display_name_corporate_suffixes(self):
        self.assertEqual(
            data.display_name("THE FAMILY HEALTH CENTERS OF GEORGIA, INC."),
            "The Family Health Centers of Georgia",
        )
        self.assertEqual(
            data.display_name("COMMUNITY HEALTH SOLUTIONS LLC"),
            "Community Health Solutions",
        )
        self.assertEqual(
            data.display_name("Fulton County Health Center"),
            "Fulton County Health Center",
        )
        self.assertEqual(data.display_name(""), "")
        self.assertEqual(data.display_name(None), "")

    def test_saturdays_format_and_count(self):
        # November 2026 has Saturdays on 7, 14, 21, 28
        sats = data.saturdays("2026-11")
        self.assertEqual(len(sats), 4)
        self.assertEqual(sats, ["2026-11-07", "2026-11-14", "2026-11-21", "2026-11-28"])
        for s in sats:
            d = dt.date.fromisoformat(s)
            self.assertEqual(d.weekday(), 5)  # 5 is Saturday

    def test_saturdays_default_next_month(self):
        sats = data.saturdays()
        self.assertGreaterEqual(len(sats), 4)
        for s in sats:
            d = dt.date.fromisoformat(s)
            self.assertEqual(d.weekday(), 5)

    def test_select_stops_logic(self):
        mock_ranked = [
            # Stop 1 (highest need)
            {"geo_id": "13121000100", "km_to_safety_net": 5.0, "latitude": 33.70, "longitude": -84.40},
            # Stop 2 (very close to Stop 1, should be skipped under min_spacing_km=5)
            {"geo_id": "13121000200", "km_to_safety_net": 4.5, "latitude": 33.71, "longitude": -84.41},
            # Stop 3 (too close to safety net, < 3km, should be skipped)
            {"geo_id": "13121000300", "km_to_safety_net": 1.5, "latitude": 33.85, "longitude": -84.30},
            # Stop 4 (valid, far enough from Stop 1)
            {"geo_id": "13121000400", "km_to_safety_net": 6.0, "latitude": 33.85, "longitude": -84.45},
            # Stop 5 (valid)
            {"geo_id": "13121000500", "km_to_safety_net": 4.0, "latitude": 33.95, "longitude": -84.35},
            # Stop 6 (valid)
            {"geo_id": "13121000600", "km_to_safety_net": 7.0, "latitude": 34.05, "longitude": -84.25},
        ]
        chosen = data.select_stops(mock_ranked, stops=4, min_spacing_km=5.0, min_km_to_safety_net=3.0)
        chosen_ids = [c["geo_id"] for c in chosen]

        self.assertIn("13121000100", chosen_ids)
        self.assertNotIn("13121000200", chosen_ids)  # Spacing violation
        self.assertNotIn("13121000300", chosen_ids)  # Under safety-net threshold
        self.assertIn("13121000400", chosen_ids)
        self.assertIn("13121000500", chosen_ids)
        self.assertIn("13121000600", chosen_ids)
        self.assertEqual(len(chosen), 4)

    def test_select_stops_exclude_and_include(self):
        mock_ranked = [
            {"geo_id": "13121000100", "km_to_safety_net": 5.0, "latitude": 33.70, "longitude": -84.40},
            {"geo_id": "13121000200", "km_to_safety_net": 5.0, "latitude": 33.80, "longitude": -84.40},
            {"geo_id": "13121000300", "km_to_safety_net": 5.0, "latitude": 33.90, "longitude": -84.40},
        ]
        # Exclude highest need
        chosen = data.select_stops(mock_ranked, stops=2, exclude=["13121000100"])
        chosen_ids = [c["geo_id"] for c in chosen]
        self.assertNotIn("13121000100", chosen_ids)
        self.assertEqual(chosen_ids, ["13121000200", "13121000300"])

        # Force include lower need
        chosen_inc = data.select_stops(mock_ranked, stops=2, include=["13121000300"])
        self.assertEqual(chosen_inc[0]["geo_id"], "13121000300")


if __name__ == "__main__":
    unittest.main()
