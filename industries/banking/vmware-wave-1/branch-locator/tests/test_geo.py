import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import geo  # noqa: E402

BRANCHES = [
    {"name": "A", "address": "1 St", "lat": 10.0, "lon": -30.0, "opens": "08:30", "closes": "16:30"},
    {"name": "B", "address": "2 St", "lat": 10.1, "lon": -30.0, "opens": "08:30", "closes": "16:30"},
    {"name": "C", "address": "3 St", "lat": 9.95, "lon": -30.0, "opens": "08:30", "closes": "16:30"},
]


class GeoTest(unittest.TestCase):
    def test_distance_one_tenth_degree(self):
        self.assertAlmostEqual(geo.distance_km(10.0, -30.0, 10.1, -30.0), 11.12, places=1)

    def test_nearest_sorted_and_limited(self):
        rows = geo.nearest(BRANCHES, 10.0, -30.0, "09:00", limit=2)
        self.assertEqual([r["name"] for r in rows], ["A", "C"])
        self.assertTrue(rows[0]["open_now"])

    def test_closed_at_closing_time(self):
        self.assertFalse(geo.is_open("08:30", "16:30", "16:30"))

    def test_python2_rounding(self):
        for distance, expected in ((1.125, 1.13), (2.675, 2.67), (1.375, 1.38)):
            with patch.object(geo, "distance_km", return_value=distance):
                self.assertEqual(geo.nearest(BRANCHES[:1], 10, -30, "09:00")[0]["km"], expected)

    def test_empty_branches(self):
        self.assertEqual(geo.nearest([], 10, -30, "09:00"), [])


if __name__ == "__main__":
    unittest.main()
