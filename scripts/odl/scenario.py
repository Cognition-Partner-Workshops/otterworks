"""Tenant-locked ODL ingress load and lifecycle control."""

import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

HERE = Path(__file__).resolve().parent
STATE = HERE / '.state'
PIDFILE = STATE / 'odl-read-latency.pid'
LOGFILE = STATE / 'odl-read-latency.log'
READY = STATE / 'odl-read-latency.ready'
NAMESPACE = 'otterworks-odl'
URL = 'https://api-t-odl.demo.otterworks.app/api/v1/odl/customers'
SCENARIO = 'odl-read-latency'
DEFAULT_DURATION = 1800
DEFAULT_RATE = 6
DEFAULT_CONCURRENCY = 16


class ScenarioError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def kubectl(*args, input=None):
    result = subprocess.run(['kubectl', '-n', NAMESPACE, *args], input=input,
                            text=True, capture_output=True, timeout=40)
    if result.returncode:
        raise ScenarioError('kubectl failed; output withheld')
    return result.stdout


def token(duration):
    key = base64.b64decode(kubectl('get', 'secret', 'api-gateway-secrets',
                                 '-o', 'jsonpath={.data.JWT_SECRET}'), validate=True)
    if not key:
        raise ScenarioError('Tenant JWT key is empty')

    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value, separators=(',', ':')).encode()).rstrip(b'=')

    owner = 'odl-read-latency-scenario'
    data = encode({'alg': 'HS256', 'typ': 'JWT'}) + b'.' + encode({
        'sub': owner, 'user_id': owner, 'exp': int(time.time()) + duration + 120})
    return (data + b'.' + base64.urlsafe_b64encode(hmac.new(key, data, hashlib.sha256).digest()).rstrip(b'=')).decode()


def get(query, bearer):
    request = Request(URL + '?' + urlencode(query), headers={'Authorization': 'Bearer ' + bearer})
    with build_opener(NoRedirect).open(request, timeout=15) as response:
        return response.status, json.load(response)


def filter_keys(items):
    families = {'db2_cust_no': [], 'oracle_account_id': [], 'crm_contact_id': []}
    for doc in items:
        keys = doc.get('source_keys', {})
        for name in ('db2_cust_no', 'crm_contact_id'):
            if keys.get(name):
                families[name].append({name: keys[name]})
        for account in keys.get('oracle_account_ids', []):
            families['oracle_account_id'].append({'oracle_account_id': account})
    if not all(families.values()):
        raise ScenarioError('Seeded customers must contain all three source-key families')
    return [values[i % len(values)] for i in range(max(map(len, families.values())))
            for values in families.values()]


def process_start(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    if fields[0] == 'Z':
        raise ProcessLookupError()
    return fields[19]


def running(record=None):
    try:
        record = record or json.loads(PIDFILE.read_text())
        pid = int(record['pid'])
        args = Path(f'/proc/{pid}/cmdline').read_bytes().decode().split('\0')
        return (pid > 1 and process_start(pid) == record['start'] and os.getpgid(pid) == pid
                and args[1:4] == [str(HERE / 'scenario.py'), '--worker', record['marker']])
    except (OSError, ValueError, KeyError, IndexError):
        return False


def stop_load():
    if not running():
        PIDFILE.unlink(missing_ok=True)
        print('load=not-running')
        return
    record = json.loads(PIDFILE.read_text())
    os.killpg(record['pid'], signal.SIGTERM)
    deadline = time.monotonic() + 25
    while running(record):
        if time.monotonic() > deadline:
            raise ScenarioError('Load still draining; PID retained, check status before retrying')
        time.sleep(.1)
    PIDFILE.unlink(missing_ok=True)
    print('load=stopped; SIGTERM drained; nothing else changed')


def local_load_running():
    if running():
        return True
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal():
            continue
        try:
            args = (process / 'cmdline').read_bytes().decode().split('\0')
            if (len(args) > 3 and Path(args[1]).parts[-3:] == ('scripts', 'odl', 'scenario.py')
                    and args[2] == '--worker'):
                process_start(int(process.name))
                return True
        except (OSError, UnicodeError, IndexError):
            continue
    return False


def reset():
    if local_load_running():
        raise ScenarioError('Load is running on this VM; disarm and drain before reset')
    data = json.loads(kubectl('get', 'secret', 'operational-data-layer-mongo', '-o', 'json'))['data']
    credentials = {key: base64.b64decode(data[key], validate=True).decode()
                   for key in ('username', 'password')}
    if not all(credentials.values()):
        raise ScenarioError('Tenant Mongo credentials are empty')
    result = kubectl('exec', '-i', 'deployment/operational-data-layer', '--', 'python', '-c',
                     (HERE / 'reset_indexes.py').read_text(), input=json.dumps(credentials))
    print(json.dumps(json.loads(result)))


@contextmanager
def locked():
    STATE.mkdir(mode=0o700, exist_ok=True)
    with (STATE / 'control.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def arm(duration):
    if running():
        raise ScenarioError('Load already running; disarm first')
    marker = secrets.token_hex(12)
    READY.unlink(missing_ok=True)
    with LOGFILE.open('ab') as log:
        child = subprocess.Popen(['setsid', sys.executable, str(HERE / 'scenario.py'), '--worker',
                                  marker, str(duration)], stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=log, close_fds=True)
    record = {'pid': child.pid, 'start': process_start(child.pid), 'marker': marker}
    PIDFILE.write_text(json.dumps(record))
    deadline = time.monotonic() + 45
    while not (READY.exists() and READY.read_text() == marker):
        if child.poll() is not None:
            PIDFILE.unlink(missing_ok=True)
            raise ScenarioError('Load startup failed; see credential-free state log')
        if time.monotonic() > deadline:
            stop_load()
            raise ScenarioError('Load startup timed out')
        time.sleep(.1)
    print(f'load=running tenant=odl scenario={SCENARIO} pid={child.pid} duration={duration}s '
          f'rate={DEFAULT_RATE}/s concurrency={DEFAULT_CONCURRENCY} log={LOGFILE}')


def drive(stop, duration, bearer, queries, rate=DEFAULT_RATE, concurrency=DEFAULT_CONCURRENCY):
    lock = threading.Lock()
    slots = threading.BoundedSemaphore(concurrency)
    counts = {}
    durations = []
    shed = 0
    started = time.monotonic()

    def one(query):
        before = time.monotonic()
        try:
            status, _ = get(query, bearer)
            status = str(status)
        except HTTPError as error:
            status = str(error.code)
        except Exception:
            status = 'transport-error'
        finally:
            elapsed = time.monotonic() - before
            with lock:
                counts[status] = counts.get(status, 0) + 1
                durations.append(elapsed)
            slots.release()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        i = 0
        while not stop.is_set() and time.monotonic() - started < duration:
            if slots.acquire(blocking=False):
                pool.submit(one, queries[i % len(queries)])
            else:
                shed += 1
            i += 1
            stop.wait(1 / rate)
    durations.sort()

    def percentile(p):
        return round(durations[min(len(durations) - 1, math.ceil(len(durations) * p) - 1)], 4) if durations else None

    return {'completed': len(durations), 'statuses': counts, 'shed': shed,
            'client_p95_seconds': percentile(.95), 'client_p99_seconds': percentile(.99),
            'elapsed_seconds': round(time.monotonic() - started, 3)}


def worker(marker, duration):
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    bearer = token(duration)
    _, page = get({'limit': 100}, bearer)
    queries = filter_keys(page.get('items', []))
    print(json.dumps({'event': 'load-start', 'utc': time.time(), 'duration': duration,
                      'rate': DEFAULT_RATE, 'concurrency': DEFAULT_CONCURRENCY}), flush=True)
    READY.write_text(marker)
    try:
        summary = drive(stop, duration, bearer, queries)
        print(json.dumps({'event': 'load-end', 'utc': time.time(), **summary}), flush=True)
    finally:
        if READY.exists() and READY.read_text() == marker:
            READY.unlink()


def prometheus(queries):
    code = ('import json,sys,urllib.request,urllib.parse; qs=json.load(sys.stdin); '
            'base="http://prometheus-prometheus.monitoring.svc.cluster.local:9090/api/v1/query?"; '
            'print(json.dumps({k:json.load(urllib.request.urlopen(base+urllib.parse.urlencode({"query":v}),'
            'timeout=15))["data"]["result"] for k,v in qs.items()}))')
    return json.loads(kubectl('exec', '-i', 'deployment/operational-data-layer', '--',
                             'python', '-c', code, input=json.dumps(queries)))


def status():
    selector = '{namespace="otterworks-odl",route="/customers"}'
    queries = {name: 'odl:' + metric + selector for name, metric in (
        ('p95_seconds', 'read_request_duration_seconds:p95'),
        ('p99_seconds', 'read_request_duration_seconds:p99'),
        ('requests_per_second', 'read_requests:rate5m'))}
    queries['alerts'] = 'ALERTS{namespace="otterworks-odl",alertname=~"ODLReadLatency(Critical|High)"}'
    values = prometheus(queries)
    print('load=' + ('running' if running() else 'not-running'))
    for name in ('p95_seconds', 'p99_seconds', 'requests_per_second'):
        print(name + '=' + (values[name][0]['value'][1] if values[name] else 'no-data'))
    for alert in ('ODLReadLatencyCritical', 'ODLReadLatencyHigh'):
        states = sorted({v['metric']['alertstate'] for v in values['alerts'] if v['metric']['alertname'] == alert})
        print(alert + '=' + (','.join(states) if states else 'inactive'))


def main(args):
    os.umask(0o077)
    if len(args) == 3 and args[0] == '--worker':
        duration = int(args[2])
        if not 1 <= duration <= 1800:
            raise ScenarioError('Duration must be 1..1800 seconds')
        worker(args[1], duration)
        return
    if len(args) not in (2, 3) or args[0] not in ('arm', 'disarm', 'status', 'reset') or args[1] != SCENARIO:
        raise ScenarioError('Only arm|disarm|status|reset odl-read-latency is supported; tenant is fixed to odl')
    if len(args) == 3 and args[0] != 'arm':
        raise ScenarioError('Duration is accepted only for arm')
    duration = int(args[2]) if len(args) == 3 else DEFAULT_DURATION
    if not 1 <= duration <= 1800:
        raise ScenarioError('Duration must be 1..1800 seconds')
    with locked():
        if args[0] == 'arm':
            arm(duration)
        elif args[0] == 'disarm':
            stop_load()
        elif args[0] == 'reset':
            reset()
        else:
            status()


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except ScenarioError as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
    except Exception as error:
        print('Scenario failed: ' + type(error).__name__ + '; sensitive details withheld', file=sys.stderr)
        sys.exit(1)
