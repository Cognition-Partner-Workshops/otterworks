"""Stand-in for the internal geocoder at geo.bank.internal (10.40.2.17)."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PLACES = {"harbour": (10.010, -30.020), "market": (10.033, -30.010), "old town": (9.990, -29.977),
          "river": (10.050, -29.991), "hill": (9.970, -30.040), "lake": (10.019, -29.955)}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query).get("q", [""])[0].lower()
        hit = next((v for k, v in PLACES.items() if k in q), (10.0, -30.0))
        body = json.dumps({"lat": hit[0], "lon": hit[1]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("0.0.0.0", 8090), H).serve_forever()
