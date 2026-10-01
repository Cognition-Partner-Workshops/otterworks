// Folder browsing load for the on-call storm. Runs as the oncall-k6 Job in the
// tenant namespace (incident/oncall/k8s/k6-job.yaml) against the public API host.
//
// It signs its own HS256 token from JWT_SECRET, which the Job injects from the
// tenant's api-gateway-secrets; the secret never leaves the pod. Folder ids are
// md5('oncall-folder-<n>') as a uuid, the same derivation seed.sql uses.
import http from 'k6/http';
import { check, sleep } from 'k6';
import crypto from 'k6/crypto';
import encoding from 'k6/encoding';

const BASE = (__ENV.API_BASE_URL || '').replace(/\/+$/, '');
const JWT_SECRET = __ENV.JWT_SECRET || '';
const OWNER_ID = __ENV.OWNER_ID || '';
const OWNER_EMAIL = __ENV.DEMO_USER_EMAIL || 'oncall-demo@otterworks.example';
const FOLDERS = parseInt(__ENV.SEED_FOLDERS || '400', 10);
const VUS = parseInt(__ENV.LOAD_VUS || '6', 10);
const MINUTES = parseFloat(__ENV.LOAD_MINUTES || '25');
const SLO_MS = Math.round(parseFloat(__ENV.P95_SLO_SECONDS || '0.5') * 1000);
const MAX_ERROR_RATIO = parseFloat(__ENV.MAX_ERROR_RATIO || '0.05');
const THINK_MIN = parseFloat(__ENV.THINK_MIN_SECONDS || '1');
const THINK_MAX = parseFloat(__ENV.THINK_MAX_SECONDS || '3');

export const options = {
  scenarios: {
    folders: {
      executor: 'constant-vus',
      vus: VUS,
      duration: `${Math.round(MINUTES * 60)}s`,
      gracefulStop: '30s',
    },
  },
  thresholds: {
    'http_req_duration{endpoint:folder_list}': [`p(95)<${SLO_MS}`],
    'http_req_failed{endpoint:folder_list}': [`rate<${MAX_ERROR_RATIO}`],
  },
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  userAgent: 'oncall-storm-k6/1.0',
};

function b64url(input) {
  return encoding.b64encode(input, 'rawurl');
}

function signToken(now) {
  const header = b64url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const claims = b64url(JSON.stringify({
    sub: OWNER_ID,
    user_id: OWNER_ID,
    email: OWNER_EMAIL,
    iat: now,
    exp: now + Math.ceil(MINUTES * 60) + 3600,
  }));
  const signature = crypto.hmac('sha256', JWT_SECRET, `${header}.${claims}`, 'binary');
  return `${header}.${claims}.${b64url(signature)}`;
}

export function folderId(n) {
  const h = crypto.md5(`oncall-folder-${n}`, 'hex');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export function setup() {
  if (!BASE || !JWT_SECRET || !OWNER_ID) {
    throw new Error('API_BASE_URL, JWT_SECRET and OWNER_ID are required');
  }
  return { token: signToken(Math.floor(Date.now() / 1000)) };
}

export default function (data) {
  const folder = folderId(Math.floor(Math.random() * FOLDERS));
  const res = http.get(`${BASE}/api/v1/documents/?folder_id=${folder}&page=1&size=50`, {
    headers: { Authorization: `Bearer ${data.token}`, Accept: 'application/json' },
    tags: { endpoint: 'folder_list', name: 'GET /api/v1/documents/?folder_id' },
    timeout: '15s',
  });
  check(res, { 'folder list is 200': (r) => r.status === 200 });
  sleep(THINK_MIN + Math.random() * (THINK_MAX - THINK_MIN));
}

function metricValue(data, name, key) {
  const m = data.metrics[name];
  return m && m.values && m.values[key] !== undefined ? m.values[key] : null;
}

export function handleSummary(data) {
  const durationKey = 'http_req_duration{endpoint:folder_list}';
  const failedKey = 'http_req_failed{endpoint:folder_list}';
  const thresholds = {};
  for (const [name, metric] of Object.entries(data.metrics)) {
    if (metric.thresholds) {
      thresholds[name] = Object.values(metric.thresholds).every((t) => t.ok);
    }
  }
  const summary = {
    tenant: __ENV.TENANT || '',
    run_id: __ENV.RUN_ID || '',
    base_url: BASE,
    vus: VUS,
    minutes: MINUTES,
    requests: metricValue(data, 'http_reqs', 'count'),
    request_rate: metricValue(data, 'http_reqs', 'rate'),
    p95_ms: metricValue(data, durationKey, 'p(95)'),
    p99_ms: metricValue(data, durationKey, 'p(99)'),
    median_ms: metricValue(data, durationKey, 'med'),
    error_ratio: metricValue(data, failedKey, 'rate'),
    p95_slo_ms: SLO_MS,
    thresholds,
    passed: Object.values(thresholds).every(Boolean),
  };
  const fmt = (v, digits) => (v === null ? 'n/a' : Number(v).toFixed(digits));
  const text = [
    `oncall-storm k6 ${summary.tenant} run ${summary.run_id}: ${summary.vus} VUs, ${summary.minutes} min`,
    `  folder list p95 ${fmt(summary.p95_ms, 0)} ms (SLO ${SLO_MS} ms), p99 ${fmt(summary.p99_ms, 0)} ms`,
    `  requests ${fmt(summary.requests, 0)}, error ratio ${fmt(summary.error_ratio, 4)}`,
    `  thresholds ${summary.passed ? 'PASS' : 'FAIL'}`,
  ].join('\n');
  return { stdout: `${text}\nK6_SUMMARY_JSON ${JSON.stringify(summary)}\n` };
}
