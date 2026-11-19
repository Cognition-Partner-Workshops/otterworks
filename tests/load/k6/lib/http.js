import http from 'k6/http';
import { check } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { baseURL } from './config.js';

export const rateLimited = new Counter('rate_limited');
export const serverErrors = new Rate('server_errors');
export const endpointRequests = new Counter('endpoint_requests');
const authFailures = new Rate('auth_failures');
const readLatency = new Trend('otterworks_read_latency', true);

export function request(method, path, endpoint, token, body = null, expected = [200], phase = 'journey', absolute = false) {
  const multipart = body && typeof body !== 'string';
  const kind = endpoint === 'health' ? 'health' : method === 'GET' ? 'read' : 'write';
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  if (body && !multipart) headers['Content-Type'] = 'application/json';
  const response = http.request(method, absolute ? path : `${baseURL}${path}`, body, {
    headers, tags: { name: endpoint, endpoint, phase, kind }, timeout: '15s', redirects: 0,
    responseCallback: http.expectedStatuses(...expected),
  });
  rateLimited.add(response.status === 429 ? 1 : 0, { endpoint, phase });
  endpointRequests.add(1, { endpoint, phase });
  authFailures.add(response.status === 401 || response.status === 403, { endpoint, phase });
  if (kind === 'read') readLatency.add(response.timings.duration, { name: endpoint, phase });
  serverErrors.add(response.status === 0 || response.status >= 500, { endpoint, phase });
  check(response, { [`${endpoint}: expected status`]: (r) => expected.includes(r.status) }, { endpoint, phase });
  if (phase === 'preflight' && !expected.includes(response.status)) {
    throw new Error(`Preflight ${endpoint}: unexpected HTTP ${response.status}`);
  }
  return response;
}

export function json(response) {
  try { return response.json(); } catch (_) { return null; }
}

export function requireJSON(response, field) {
  const data = json(response);
  if (response.status < 200 || response.status >= 300 || !data || !data[field]) {
    throw new Error(`Setup failed: status ${response.status}, missing ${field}`);
  }
  return data;
}
