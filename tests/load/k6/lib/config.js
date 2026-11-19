export const profiles = ['smoke', 'load', 'baseline', 'peak', 'stress', 'spike', 'soak'];
export const endpoints = [
  'login', 'documents_list', 'document_get', 'document_create', 'document_update',
  'documents_search', 'search', 'files_list', 'folders_list', 'file_upload',
  'file_download', 'file_content', 'file_delete', 'document_delete', 'notifications_unread',
];

function positive(value, fallback, name) {
  const number = Number(value === undefined || value === '' ? fallback : value);
  if (!Number.isFinite(number) || number <= 0) throw new Error(`${name} must be positive`);
  return number;
}

export const profile = __ENV.PROFILE || 'smoke';
if (!profiles.includes(profile)) throw new Error(`Unknown PROFILE: ${profile}`);
export const baseURL = (__ENV.BASE_URL === undefined ? 'http://localhost:8080' : __ENV.BASE_URL).replace(/\/+$/, '');
if (!/^https?:\/\/[^/?#@]+(?::\d+)?$/i.test(baseURL)) {
  throw new Error('BASE_URL must be an explicit HTTP(S) API origin (no credentials/path/query)');
}
export const readOnly = __ENV.READ_ONLY === '1';
const main = /(?:^|[.\/-])(?:api-)?t-main(?:[.:/-]|$)|otterworks-main/i.test(baseURL);
if (main && !(readOnly && profile === 'smoke' && __ENV.ALLOW_MAIN === '1')) {
  throw new Error('Main is protected: only READ_ONLY=1 smoke with explicit ALLOW_MAIN=1 is allowed');
}
export const rateScale = positive(__ENV.RATE, 1, 'RATE');
export const vuScale = positive(__ENV.VUS, 1, 'VUS');
const targetVUs = Math.ceil(positive(__ENV.TARGET_VUS, 50, 'TARGET_VUS') * vuScale);
export const userCount = positive(__ENV.USERS, 10, 'USERS');
if (!Number.isInteger(userCount) || userCount > 200) throw new Error('USERS must be an integer in 1..200');
export const runID = __ENV.RUN_ID || `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
if (!/^[a-zA-Z0-9-]{1,60}$/.test(runID)) throw new Error('RUN_ID must be 1..60 alphanumeric/hyphen characters');

function seconds(value, name = 'DURATION') {
  const match = /^(\d+(?:\.\d+)?)(s|m|h)$/.exec(value);
  if (!match || Number(match[1]) <= 0) throw new Error(`${name} must use s, m or h`);
  return Number(match[1]) * ({ s: 1, m: 60, h: 3600 })[match[2]];
}

export function buildOptions() {
  const defaults = {
    baseline: [[30, 10], [240, 10], [30, 0]],
    peak: [[30, 30], [240, 30], [30, 0]],
    load: [[120, targetVUs], [seconds(__ENV.HOLD || '10m', 'HOLD'), targetVUs], [120, 0]],
    stress: [[120, targetVUs], [180, targetVUs * 2], [180, targetVUs * 3], [180, targetVUs * 4], [120, 0]],
    spike: [[60, Math.ceil(targetVUs / 10)], [20, targetVUs], [180, targetVUs], [20, Math.ceil(targetVUs / 10)], [120, Math.ceil(targetVUs / 10)]],
    soak: [[300, targetVUs], [3600, targetVUs], [300, 0]],
  };
  let scenario;
  if (profile === 'smoke') {
    scenario = { executor: 'constant-vus', vus: Math.min(2, Math.ceil(2 * vuScale)), duration: __ENV.DURATION || '1m' };
    seconds(scenario.duration);
  } else {
    const stages = defaults[profile];
    const total = stages.reduce((sum, stage) => sum + stage[0], 0);
    const timeScale = __ENV.DURATION ? seconds(__ENV.DURATION) / total : 1;
    scenario = {
      executor: 'ramping-arrival-rate', startRate: 0, timeUnit: '1s',
      preAllocatedVUs: Math.ceil(30 * vuScale), maxVUs: Math.ceil(150 * vuScale),
      stages: stages.map(([duration, target]) => ({
        duration: `${Math.max(1, Math.round(duration * timeScale))}s`,
        target: Math.round(target * (['baseline', 'peak'].includes(profile) ? rateScale : 1)),
      })),
    };
    if (!['baseline', 'peak'].includes(profile)) {
      scenario = { executor: 'ramping-vus', startVUs: 0, stages: scenario.stages };
    }
  }
  const slo = (expression, correctness = false) => ({ threshold: expression, abortOnFail: profile === 'smoke' && correctness, delayAbortEval: '10s' });
  const thresholds = {
    http_req_failed: [slo('rate<0.01', true)],
    'http_req_failed{phase:journey}': [slo('rate<0.01', true)],
    'http_req_duration{phase:journey}': [slo('p(95)<500'), slo('p(99)<1500')],
    'http_req_duration{kind:read}': [slo('p(95)<800'), slo('p(99)<1500')],
    'http_req_duration{kind:health}': [slo('p(95)<300')],
    checks: [slo('rate>0.99', true)],
    rate_limited: ['count==0'],
    server_errors: [slo('rate<0.01', true)],
  };
  if (['baseline', 'peak'].includes(profile)) thresholds.dropped_iterations = ['count==0'];
  for (const endpoint of readOnly ? [] : endpoints) {
    thresholds[`http_req_failed{endpoint:${endpoint},phase:journey}`] = [slo('rate<0.01', true)];
    const reads = ['documents_list', 'document_get', 'documents_search', 'search', 'files_list', 'folders_list', 'file_content', 'file_download', 'notifications_unread'];
    thresholds[`http_req_duration{endpoint:${endpoint},phase:journey}`] = [slo(`p(95)<${endpoint === 'login' ? 1000 : reads.includes(endpoint) ? 800 : 500}`), slo('p(99)<1500')];
    thresholds[`endpoint_requests{endpoint:${endpoint},phase:journey}`] = ['count>0'];
  }
  return {
    scenarios: { [profile]: { ...scenario, gracefulStop: '15s' } }, thresholds,
    setupTimeout: '5m', summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(95)', 'p(99)'],
    systemTags: ['status', 'method', 'name', 'scenario', 'expected_response'],
  };
}
