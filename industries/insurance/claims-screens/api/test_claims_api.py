"""Auth and masking at the HTTP boundary, over the BizTalk goldens: python3 -m unittest discover -s api"""
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import claims_api as api  # noqa: E402

READER, ADJUSTER = "reader-token-0123456789", "adjuster-token-0123456789"


class ClaimsApiAuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tokens = api.tokens_from_env({"CLAIMS_SCREENS_READER_TOKEN": READER, "CLAIMS_SCREENS_ADJUSTER_TOKEN": ADJUSTER})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), api.make_handler(api.Golden(), tokens))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}/api/claims-screens"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path, token=None, method="GET"):
        req = urllib.request.Request(self.base + path, method=method)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def test_every_route_rejects_a_missing_or_wrong_token(self):
        for method, path in [("GET", "/source"), ("GET", "/fnol"), ("POST", "/fnol/CLM-2026-100405"),
                             ("GET", "/claims/CLM-2026-100405"), ("GET", "/payments/PI-2026-880107")]:
            for token in (None, "not-a-valid-token-at-all"):
                with self.subTest(method=method, path=path, token=token):
                    code, body = self.get(path, token, method)
                    self.assertEqual(code, 401)
                    self.assertNotIn("claimant", body)

    def test_reader_gets_the_claimant_masked(self):
        code, body = self.get("/claims/CLM-2026-100405", READER)
        self.assertEqual(code, 200)
        self.assertEqual(body["claimant"], "P**** V***********")

    def test_adjuster_gets_the_claimant_in_clear(self):
        code, body = self.get("/claims/CLM-2026-100405", ADJUSTER)
        self.assertEqual(code, 200)
        self.assertEqual(body["claimant"], "Priya Venkataraman")

    def test_reader_gets_a_claimant_payee_masked_in_instruction_and_remittance(self):
        code, body = self.get("/payments/PI-2026-880107", READER)
        self.assertEqual(code, 200)
        self.assertEqual(body["payee"], {"name": "I***** C**********", "type": "CL", "account": "****1511"})
        self.assertEqual({l["payee"] for l in body["remittance"]["lines"]}, {"I***** C**********"})
        self.assertNotIn("Imogen", json.dumps(body))

    def test_adjuster_gets_a_claimant_payee_in_clear(self):
        code, body = self.get("/payments/PI-2026-880107", ADJUSTER)
        self.assertEqual(code, 200)
        self.assertEqual(body["payee"]["name"], "Imogen Castellanos")
        self.assertEqual({l["payee"] for l in body["remittance"]["lines"]}, {"Imogen Castellanos"})

    def test_business_payee_stays_readable_for_a_reader(self):
        code, body = self.get("/payments/PI-2026-880100", READER)
        self.assertEqual(code, 200)
        self.assertEqual(body["payee"]["name"], "Harbour Collision Repair")
        self.assertEqual({l["payee"] for l in body["remittance"]["lines"]}, {"Harbour Collision Repair"})

    def test_tokens_must_be_configured_long_and_distinct(self):
        with self.assertRaises(ValueError):
            api.tokens_from_env({})
        with self.assertRaises(ValueError):
            api.tokens_from_env({"CLAIMS_SCREENS_READER_TOKEN": "short"})
        with self.assertRaises(ValueError):
            api.tokens_from_env({"CLAIMS_SCREENS_READER_TOKEN": READER, "CLAIMS_SCREENS_ADJUSTER_TOKEN": READER})

    def test_masks_match_the_compliance_kit(self):
        self.assertEqual(api.mask_name("Imogen  Castellanos"), "I***** C**********")
        self.assertIsNone(api.mask_name(""))
        self.assertEqual(api.mask_account("12-3456-7890"), "XX-XXXX-7890")
        self.assertEqual(api.mask_account("****1511"), "****1511")


if __name__ == "__main__":
    unittest.main()
