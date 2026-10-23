import unittest

from server import route


class RouteTest(unittest.TestCase):
    def test_health(self):
        self.assertEqual(route("/health"), (200, {"status": "UP"}))

    def test_unknown(self):
        self.assertEqual(route("/nope")[0], 404)


if __name__ == "__main__":
    unittest.main()
