import os
import socket
import ssl
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import readiness

SCRIPT = Path(__file__).resolve().parents[4] / "scripts/lp-local.sh"


class StartupTest(unittest.TestCase):
    def test_up_reloads_data_api_even_when_shared_material_is_already_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            mock_env = Path(tmp) / "bash-env"
            calls = Path(tmp) / "docker-calls"
            mock_env.write_text(
                'docker() {\n'
                '  printf "%s\\n" "$*" >> "$DOCKER_CALLS"\n'
                '  if [[ "$*" == *"exec -T dataapi python3 /app/readiness.py" ]] && [ ! -e "$DOCKER_CALLS.probed" ]; then\n'
                '    touch "$DOCKER_CALLS.probed"\n'
                '    return 1\n'
                '  fi\n'
                '}\n'
                'curl() { return 0; }\n'
                'sleep() { return 0; }\n'
            )
            subprocess.run(
                ["bash", SCRIPT, "up"],
                env={**os.environ, "BASH_ENV": str(mock_env), "DOCKER_CALLS": str(calls),
                     "RUN_TOKEN": "STARTUP_TEST"},
                check=True, capture_output=True, text=True,
            )
            commands = calls.read_text().splitlines()

        def command_index(suffix):
            return next(i for i, command in enumerate(commands) if command.endswith(suffix))

        self.assertLess(command_index("run --rm --no-deps -T certs"), command_index("up -d --build"))
        self.assertLess(command_index("up -d --build"), command_index("restart dataapi"))
        self.assertLess(command_index("restart dataapi"),
                        command_index("restart fn-announcements fn-preferences fn-feedback"))
        first, retry = (i for i, command in enumerate(commands)
                        if command.endswith("exec -T dataapi python3 /app/readiness.py"))
        self.assertLess(command_index("restart dataapi"), first)
        self.assertLess(first, retry)
        self.assertLess(retry, command_index("restart fn-announcements fn-preferences fn-feedback"))

    def test_readiness_reaches_both_listeners_without_a_proxy(self):
        requests = []

        class PingHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append((self.server.server_port, self.path))
                self.send_response(200 if self.path == "/ping" else 404)
                self.end_headers()

            def log_message(self, *args):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            cert, key = Path(tmp) / "server.pem", Path(tmp) / "server.key"
            subprocess.run(
                ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                 "-subj", "/CN=dataapi", "-addext", "subjectAltName=DNS:dataapi",
                 "-out", cert, "-keyout", key],
                check=True, capture_output=True,
            )
            with (HTTPServer(("127.0.0.1", 0), PingHandler) as http,
                  HTTPServer(("127.0.0.1", 0), PingHandler) as https,
                  ThreadPoolExecutor(2) as pool):
                tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                tls.load_cert_chain(cert, key)
                https.socket = tls.wrap_socket(https.socket, server_side=True)
                for server in (http, https):
                    server.timeout = 3
                    pool.submit(server.handle_request)
                ports = {("127.0.0.1", 8080): http.server_port, ("dataapi", 443): https.server_port}
                resolve = socket.getaddrinfo

                def local_address(host, port, *args):
                    return resolve("127.0.0.1", ports[host, port], *args)

                proxy = "http://127.0.0.1:9"
                with (patch("socket.getaddrinfo", side_effect=local_address),
                      patch.dict(os.environ, {"https_proxy": proxy, "HTTPS_PROXY": proxy,
                                              "http_proxy": proxy, "HTTP_PROXY": proxy,
                                              "no_proxy": "", "NO_PROXY": ""})):
                    readiness.check(cert)
                self.assertEqual(requests, [(http.server_port, "/ping"), (https.server_port, "/ping")])
