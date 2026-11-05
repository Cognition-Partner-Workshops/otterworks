"""Security pages use the same capture contract as existing receivers."""

import json
import tempfile
import threading
import unittest
from http.server import HTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import alert_sink


class SecurityReceiverTest(unittest.TestCase):
    def test_capture_latest_and_clear(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            alert_sink, "DATA_DIR", directory
        ):
            server = HTTPServer(("127.0.0.1", 0), alert_sink.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                for receiver in alert_sink.RECEIVERS:
                    with urlopen(base + f"/{receiver}/latest") as response:
                        self.assertIsNone(json.load(response))
                    request = Request(
                        base + f"/{receiver}",
                        data=b'{"alerts":[]}',
                        headers={"X-Webhook-Secret": "test-only"},
                    )
                    with urlopen(request) as response:
                        self.assertEqual(response.status, 200)
                    with urlopen(base + f"/{receiver}/latest") as response:
                        record = json.load(response)
                    self.assertEqual(record["receiver"], receiver)
                    self.assertEqual(record["payload"], {"alerts": []})
                    self.assertEqual(
                        record["headers"]["X-Webhook-Secret"], "<redacted>"
                    )
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base + "/unknown", data=b"{}"))
                self.assertEqual(error.exception.code, 404)
                with urlopen(Request(base, method="DELETE")) as response:
                    self.assertEqual(response.status, 200)
                with urlopen(base + "/security/latest") as response:
                    self.assertIsNone(json.load(response))
            finally:
                server.shutdown()
                thread.join()
                server.server_close()
