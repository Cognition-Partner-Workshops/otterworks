import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jobs/py"))
from user_pref_json_flatten import preferences


class PreferencesTest(unittest.TestCase):
    def test_legacy_semantics(self):
        for raw in (None, "", "{}", "{", "null", "true", "42", '"text"',
                    '{"theme":null,"notifications":false,"locale":3}',
                    '{"theme":[1,true],"notifications":{"a":null},"locale":"en"}',
                    '{"theme":"dark","theme":"light","locale":"日本語"}'):
            with self.subTest(raw=raw):
                def legacy(key):
                    try:
                        return str(json.loads(raw or "{}").get(key, ""))
                    except (ValueError, TypeError):
                        return None
                try:
                    expected = tuple(legacy(key) for key in ("theme", "notifications", "locale"))
                except AttributeError:
                    with self.assertRaises(AttributeError):
                        preferences(raw)
                else:
                    self.assertEqual(preferences(raw), expected)


if __name__ == "__main__":
    unittest.main()
