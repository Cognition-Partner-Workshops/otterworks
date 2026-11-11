# run_token=dbx-d1111 expires=2026-11-24
import math
import unittest

from job import score


class ScoreTests(unittest.TestCase):
    def test_source_formula_and_case_sensitive_status(self):
        for customer in (-51, -1, 0, 1, 49, 50, 999999):
            for status in (None, "closed", "CLOSED", "closed ", "active"):
                expected = 1 / (1 + math.exp(-(-1.8 + .04 * (customer % 50) + (1.2 if status == "closed" else 0))))
                self.assertEqual(score(status, customer), expected)

    def test_null_customer_keeps_source_error(self):
        with self.assertRaises(TypeError):
            score("closed", None)


if __name__ == "__main__":
    unittest.main()
