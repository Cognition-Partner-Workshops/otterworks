// OtterWorks load test (k6). Drives the API gateway through the shared ingress
// with the same read-heavy mix a browser session produces.
//
//   k6 run -e BASE_URL=https://api-t-<id>.<domain> -e PROFILE=load tests/load/k6/otterworks.js
//
// PROFILE: smoke (1 min, 2 VUs) | load (original VU model) | baseline | peak |
//          stress (ramp past peak to find the knee) | spike (sudden 10x) | soak (1h)
// TARGET_VUS scales load/stress/spike (default 50). READ_ONLY=1 skips the
// login/registration setup and only exercises unauthenticated health routes,
// which is the only mode allowed against t-main.
import { group, sleep } from 'k6';
import { buildOptions, readOnly as READ_ONLY } from './lib/config.js';
import { setup as setupBusySeason, iteration, handleSummary } from './busy-season.js';
import { request } from './lib/http.js';

export const options = buildOptions();
export { handleSummary };

export function setup() {
  if (READ_ONLY) return { token: null };
  return setupBusySeason();
}

export default function (data) {
  group('health', () => {
    request('GET', '/health', 'health', null);
  });
  if (READ_ONLY) { sleep(1); return; }

  group('browse', () => {
    iteration(data);
  });
}
