
import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]


class ComplianceFlagRulesTest(unittest.TestCase):
    def test_disposition_handler(self):
        namespace = {}
        module = ast.parse(_run_render((ROOT / "warehouse/snowpark/compliance_flag_rules.py").read_text()))
        handler = next(node.value for node in module.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == "DISPOSITION_HANDLER"
                               for target in node.targets))
        # The handler is a literal in this fixed, reviewed repository module, not caller input.
        exec(ast.literal_eval(handler), namespace)  # nosemgrep: python.lang.security.audit.exec-detected.exec-detected
        disposition = namespace["disposition"]
        for status, severity, expected in (
            ("closed", 7000, "resolved"),
            ("closed", None, "resolved"),
            ("open", 7001, "review"),
            ("open", 7000, "review"),
            ("open", 6999, "monitor"),
            ("open", None, "monitor"),
            ("Closed", 0, "monitor"),
            ("Closed", 7000, "review"),
            ("closed ", 0, "monitor"),
            ("", 0, "monitor"),
            (None, None, "monitor"),
            (None, 7000, "review"),
        ):
            with self.subTest(status=status, severity=severity):
                self.assertEqual(disposition(status, severity), expected)


if __name__ == "__main__":
    unittest.main()
