import json
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ECHO = '''
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class Echo(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(503 if self.path.endswith('/error') else 200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(dict(self.headers)).encode())

HTTPServer(('0.0.0.0', 8080), Echo).serve_forever()
'''


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def main():
    name = 'nginx-proto-' + uuid.uuid4().hex[:12]
    upstream = name + '-upstream'
    nginx = name + '-web'
    dockerfile = (ROOT / 'Dockerfile').read_text()
    image = re.findall(r'^FROM (\S+)', dockerfile, re.MULTILINE)[-1]
    env_filter = re.search(r'NGINX_ENVSUBST_FILTER="([^"]+)"', dockerfile)[1]
    docker('network', 'create', name)
    try:
        docker('run', '-d', '--name', upstream, '--network', name,
               'python:3.12-alpine', 'python', '-u', '-c', ECHO)
        docker('run', '-d', '--name', nginx, '--network', name,
               '-p', '127.0.0.1::3000',
               '-v', f'{ROOT / "nginx/default.conf.template"}:/etc/nginx/templates/default.conf.template:ro',
               '-v', f'{ROOT / "nginx/19-admin-upstream.envsh"}:/docker-entrypoint.d/19-admin-upstream.envsh:ro',
               '-e', f'API_GATEWAY_URL=http://{upstream}:8080',
               '-e', f'ADMIN_DASHBOARD_URL=http://{upstream}:8080',
               '-e', 'NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1',
               '-e', f'NGINX_ENVSUBST_FILTER={env_filter}', image)
        port = json.loads(docker('inspect', nginx))[0]['NetworkSettings']['Ports']['3000/tcp'][0]['HostPort']
        base = 'http://127.0.0.1:' + port
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(base + '/api/health', timeout=2) as response:
                    assert response.status == 200
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)
        print(docker('exec', nginx, 'nginx', '-t'))
        rendered = docker('exec', nginx, 'cat', '/etc/nginx/conf.d/default.conf')
        for variable in ('$http_x_forwarded_proto', '$forwarded_proto', '$scheme',
                         '$proxy_add_x_forwarded_for', '$host'):
            assert variable in rendered, variable + ' lost during envsubst'
        assert '${API_GATEWAY_URL}' not in rendered
        assert '${ADMIN_DASHBOARD_URL}' not in rendered
        print('envsubst: nginx variables preserved; upstream URLs substituted')
        for path in ('/api/v1/headers', '/admin/headers'):
            for protocol in ('https', 'http', None, ''):
                headers = {'Host': 'tenant.example', 'X-Forwarded-For': '203.0.113.10'}
                if protocol is not None:
                    headers['X-Forwarded-Proto'] = protocol
                request = urllib.request.Request(base + path, headers=headers)
                with urllib.request.urlopen(request, timeout=5) as response:
                    assert response.status == 200
                    received = json.load(response)
                expected = protocol or 'http'
                assert received['X-Forwarded-Proto'] == expected, received
                assert received['Host'] == 'tenant.example', received
                assert received['X-Forwarded-For'].startswith('203.0.113.10, '), received
                print(f'{path}: incoming={protocol!r} upstream={expected} HTTP 200; Host and X-Forwarded-For preserved')
            request = urllib.request.Request(base + path + '/error',
                                             headers={'X-Forwarded-Proto': 'https'})
            try:
                urllib.request.urlopen(request, timeout=5)
            except urllib.error.HTTPError as error:
                assert error.code == 503
                assert json.load(error)['X-Forwarded-Proto'] == 'https'
                print(f'{path}/error: upstream HTTP 503 and https preserved')
            else:
                raise AssertionError('Expected upstream HTTP 503')
        print('PASS: forwarded protocol smoke test')
    finally:
        for container in (nginx, upstream):
            subprocess.run(['docker', 'rm', '-f', container], check=False, capture_output=True)
        docker('network', 'rm', name)


if __name__ == '__main__':
    main()
