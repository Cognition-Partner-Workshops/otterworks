// OtterWorks load test (k6). Drives the API gateway through the shared ingress
// with the same read-heavy mix a browser session produces.
//
//   k6 run -e BASE_URL=https://api-t-<id>.<domain> -e PROFILE=load tests/load/k6/otterworks.js
//
// PROFILE: smoke (1 min, 2 VUs) | load (busy-season expected peak) |
//          stress (ramp past peak to find the knee) | spike (sudden 10x) | soak (1h)
// TARGET_VUS scales load/stress/spike (default 50). READ_ONLY=1 skips the
// login/registration setup and only exercises unauthenticated health routes,
// which is the only mode allowed against t-main.
import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = (__ENV.BASE_URL || 'http://localhost:8080').replace(/\/$/, '');
const PROFILE = __ENV.PROFILE || 'smoke';
const VUS = parseInt(__ENV.TARGET_VUS || '50', 10);
const READ_ONLY = __ENV.READ_ONLY === '1';
const HOLD = __ENV.HOLD || '10m'; // steady-state length of the load profile

const profiles = {
  smoke: { executor: 'constant-vus', vus: 2, duration: '1m' },
  load: {
    executor: 'ramping-vus', startVUs: 0,
    stages: [{ duration: '2m', target: VUS }, { duration: HOLD, target: VUS }, { duration: '2m', target: 0 }],
  },
  stress: {
    executor: 'ramping-vus', startVUs: 0,
    stages: [
      { duration: '2m', target: VUS }, { duration: '3m', target: VUS * 2 },
      { duration: '3m', target: VUS * 3 }, { duration: '3m', target: VUS * 4 }, { duration: '2m', target: 0 },
    ],
  },
  spike: {
    executor: 'ramping-vus', startVUs: 0,
    stages: [
      { duration: '1m', target: Math.ceil(VUS / 10) }, { duration: '20s', target: VUS },
      { duration: '3m', target: VUS }, { duration: '20s', target: Math.ceil(VUS / 10) }, { duration: '2m', target: Math.ceil(VUS / 10) },
    ],
  },
  soak: {
    executor: 'ramping-vus', startVUs: 0,
    stages: [{ duration: '5m', target: VUS }, { duration: '60m', target: VUS }, { duration: '5m', target: 0 }],
  },
};
if (!profiles[PROFILE]) throw new Error(`unknown PROFILE ${PROFILE}`);

export const options = {
  scenarios: { [PROFILE]: profiles[PROFILE] },
  thresholds: {
    // Same objectives the OtterworksMain* SLO alerts page on.
    http_req_failed: [{ threshold: 'rate<0.01', abortOnFail: PROFILE !== 'stress' }],
    'http_req_duration{kind:read}': ['p(95)<800', 'p(99)<1500'],
    'http_req_duration{kind:health}': ['p(95)<300'],
    checks: ['rate>0.99'],
  },
  summaryTrendStats: ['avg', 'p(50)', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

const authFailures = new Rate('auth_failures');
const readLatency = new Trend('otterworks_read_latency', true);

export function setup() {
  if (READ_ONLY) return { token: null };
  const email = __ENV.LOADTEST_EMAIL || `loadtest+${Date.now()}@example.com`;
  const password = __ENV.LOADTEST_PASSWORD || `Lt-${Date.now()}-pw!`;
  const json = { headers: { 'Content-Type': 'application/json' } };
  if (!__ENV.LOADTEST_EMAIL) {
    http.post(`${BASE_URL}/api/v1/auth/register`, JSON.stringify({ email, password, displayName: 'Load Test' }), json);
  }
  const res = http.post(`${BASE_URL}/api/v1/auth/login`, JSON.stringify({ email, password }), json);
  const ok = check(res, { 'login 200': (r) => r.status === 200 && !!r.json('accessToken') });
  if (!ok) throw new Error(`login failed: ${res.status} ${res.body && res.body.substring(0, 200)}`);
  return { token: res.json('accessToken') };
}

export default function (data) {
  group('health', () => {
    const r = http.get(`${BASE_URL}/health`, { tags: { kind: 'health', name: 'health' } });
    check(r, { 'health 200': (x) => x.status === 200 });
  });
  if (!data.token) { sleep(1); return; }

  const params = (name) => ({ headers: { Authorization: `Bearer ${data.token}` }, tags: { kind: 'read', name } });
  group('browse', () => {
    for (const [name, path] of [
      ['documents', '/api/v1/documents/'],
      ['files', '/api/v1/files'],
      ['notifications', '/api/v1/notifications'],
      ['search', '/api/v1/search?q=report'],
    ]) {
      const r = http.get(`${BASE_URL}${path}`, params(name));
      readLatency.add(r.timings.duration, { name });
      authFailures.add(r.status === 401 || r.status === 403);
      check(r, { [`${name} 2xx`]: (x) => x.status >= 200 && x.status < 300 });
    }
  });
  sleep(1 + Math.random() * 2);
}
