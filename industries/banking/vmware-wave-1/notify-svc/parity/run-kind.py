#!/usr/bin/env python3
"""Reset kind Redis and capture across Service and both pod port-forwards."""
import argparse
import contextlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--context', default='kind-w1-notify-svc')
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    kubectl = ['kubectl', '--context', args.context]
    subprocess.run(kubectl + ['-n', 'deps', 'rollout', 'restart', 'deploy/redis'], check=True)
    subprocess.run(kubectl + ['-n', 'deps', 'rollout', 'status', 'deploy/redis', '--timeout=120s'], check=True)
    pods = subprocess.check_output(kubectl + ['-n', 'app-notify-svc', 'get', 'pods',
        '-l', 'app=notify-svc', '-o', 'jsonpath={.items[*].metadata.name}'], text=True).split()
    if len(pods) != 2:
        raise RuntimeError('expected exactly two notify-svc replicas')
    with contextlib.ExitStack() as stack:
        upstreams = []
        for index, target in enumerate(['svc/notify-svc'] + ['pod/' + pod for pod in pods]):
            port = 18085 + index
            log = stack.enter_context((out / ('forward-%d.txt' % index)).open('w'))
            process = subprocess.Popen(kubectl + ['-n', 'app-notify-svc', 'port-forward',
                target, '%d:%d' % (port, 80 if index == 0 else 8080)], stdout=log, stderr=log)
            stack.callback(process.wait)
            stack.callback(process.terminate)
            upstreams.append((port, target))
            deadline = time.monotonic() + 90
            while True:
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                try:
                    conn.request('GET', '/health')
                    response = conn.getresponse()
                    if response.status == 200:
                        response.read()
                        break
                except (OSError, http.client.HTTPException):
                    pass
                finally:
                    conn.close()
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('port-forward/health failed: ' + target)
                time.sleep(0.25)

        routing = stack.enter_context((out / 'routing.tsv').open('w'))
        routing.write('method\tpath\tstatus\tupstream\n')
        counter = 0
        lock = threading.Lock()

        class Proxy(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def forward(self):
                nonlocal counter
                with lock:
                    port, target = upstreams[counter % len(upstreams)]
                    counter += 1
                body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                headers = dict(self.headers)
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
                try:
                    conn.request(self.command, self.path, body or None, headers)
                    response = conn.getresponse()
                    raw = response.read()
                    self.send_response_only(response.status)
                    for key, value in response.getheaders():
                        if key.lower() not in ('connection', 'transfer-encoding'):
                            self.send_header(key, value)
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.wfile.write(raw)
                    with lock:
                        routing.write('%s\t%s\t%d\t%s\n' % (
                            self.command, self.path, response.status, target))
                        routing.flush()
                finally:
                    conn.close()

            do_GET = forward
            do_POST = forward

        server = ThreadingHTTPServer(('127.0.0.1', 18084), Proxy)
        stack.callback(server.server_close)
        stack.callback(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        subprocess.run([sys.executable, str(Path(__file__).with_name('parity.py')),
            '--base', 'http://127.0.0.1:18084', '--out', str(out), '--reset-cmd', 'true'], check=True)
        for pod in pods:
            log = subprocess.check_output(kubectl + ['-n', 'app-notify-svc', 'logs', pod], text=True)
            (out / (pod + '.txt')).write_text(log)
            print('%s: %d queued lines' % (pod, sum(line.startswith('queued ') for line in log.splitlines())))


if __name__ == '__main__':
    main()
