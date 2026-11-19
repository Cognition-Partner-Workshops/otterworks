import { sleep } from 'k6';
import { request, requireJSON } from './http.js';
import { runID, userCount } from './config.js';

export function registerUsers() {
  const users = [];
  const existing = !!__ENV.LOADTEST_EMAIL;
  if (existing && !__ENV.LOADTEST_PASSWORD) throw new Error('LOADTEST_EMAIL requires LOADTEST_PASSWORD');
  for (let i = 0; i < (existing ? 1 : userCount); i++) {
    const credentials = {
      email: __ENV.LOADTEST_EMAIL || `loadtest-${runID}-${i}@example.test`,
      password: __ENV.LOADTEST_PASSWORD || `Loadtest-${runID}!9`, displayName: `Load test ${i}`,
    };
    const data = requireJSON(request('POST', `/api/v1/auth/${existing ? 'login' : 'register'}`, existing ? 'login' : 'register', null,
      JSON.stringify(credentials), [existing ? 200 : 201], 'setup'), 'accessToken');
    users.push({ ...credentials, id: data.user.id, token: data.accessToken, documents: [] });
    sleep(0.1);
  }
  return users;
}
