# run_token=dbx-d1111 expires=2026-11-24
import math
import unittest

from job import score


class ScoreTests(unittest.TestCase):
    def test_source_formula(self):
        for logins, actions in ((0, 0), (24, 450), (4448, 532), (-1, -1)):
            self.assertEqual(score(logins, actions), 1 / (1 + math.exp(-(-2.1 + logins * .0004 - actions * .0001))))

    def test_primitive_scala_udf_null_propagation(self):
        self.assertIsNone(score(None, 1))
        self.assertIsNone(score(1, None))

    def test_java_exp_overflow_returns_zero(self):
        self.assertEqual(score(0, 2147483647), 0.0)


if __name__ == "__main__":
    unittest.main()
