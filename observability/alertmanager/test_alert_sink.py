from http.client import HTTPConnection
from http.server import HTTPServer
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from threading import Thread

import pytest

SCRIPT = Path(__file__).with_name('alert_sink.py')


def test_standalone_import(tmp_path):
    script = tmp_path / 'alert_sink.py'
    script.write_bytes(SCRIPT.read_bytes())
    result = subprocess.run([sys.executable, '-I', '-c',
                             'import runpy,sys; runpy.run_path(sys.argv[1], run_name="standalone")',
                             str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def sink(tmp_path):
    spec = importlib.util.spec_from_file_location('sink', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DATA_DIR = str(tmp_path)
    server = HTTPServer(('127.0.0.1', 0), module.Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection(*server.server_address, timeout=5)
    yield connection, module
    connection.close()
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_round_trip_preserves_payload_and_redacts_headers(sink):
    connection, _ = sink
    payload = {'run': 'sfx-d1110', 'message': 'SFX_D1110_AFTER'}
    connection.request('POST', '/sink', json.dumps(payload), {'Authorization': 'fixture-only'})
    response = connection.getresponse()
    assert response.status == 200
    response.read()
    connection.request('GET', '/sink/latest')
    record = json.loads(connection.getresponse().read())
    assert record['payload'] == payload
    assert record['headers']['Authorization'] == '<redacted>'


def test_empty_receiver(sink):
    connection, _ = sink
    connection.request('GET', '/sink/latest')
    assert json.loads(connection.getresponse().read()) is None


def test_rejects_oversized_request(sink):
    connection, module = sink
    connection.request('POST', '/sink', headers={'Content-Length': str(module.MAX_BODY_BYTES + 1)})
    response = connection.getresponse()
    assert response.status == 413
    response.read()
