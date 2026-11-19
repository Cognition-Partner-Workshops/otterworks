import http from 'k6/http';
import exec from 'k6/execution';
import { check, sleep } from 'k6';
import { baseURL, profile, runID } from './lib/config.js';
import { registerUsers } from './lib/auth.js';
import { json, request, requireJSON } from './lib/http.js';

const content = 'OtterWorks busy season load fixture\n'.repeat(32);
const plan = [
  'list', 'get', 'list', 'write', 'documentSearch', 'search', 'files',
  'list', 'get', 'folders', 'unread', 'list', 'get', 'upload',
  'documentSearch', 'list', 'search', 'get', 'write', 'list', 'login',
];

function documentBody(title) {
  return JSON.stringify({ title, content, content_type: 'text/markdown' });
}

function journey(action, user, phase = 'journey') {
  const token = user.token;
  const doc = user.documents[exec.vu.idInTest % user.documents.length];
  const get = (path, endpoint) => request('GET', path, endpoint, token, null, [200], phase);
  switch (action) {
    case 'login': {
      const response = request('POST', '/api/v1/auth/login', 'login', null,
        JSON.stringify({ email: user.email, password: user.password }), [200], phase);
      const data = json(response);
      if (data && data.accessToken) user.token = data.accessToken;
      return response;
    }
    case 'list': return get('/api/v1/documents/?size=20', 'documents_list');
    case 'get': return get(`/api/v1/documents/${doc}`, 'document_get');
    case 'documentSearch': return get('/api/v1/documents/search?q=Loadtest&size=20', 'documents_search');
    case 'search': return get('/api/v1/search?q=Loadtest&size=20', 'search');
    case 'files': return get('/api/v1/files', 'files_list');
    case 'folders': return get('/api/v1/folders', 'folders_list');
    case 'unread': return get('/api/v1/notifications/unread-count', 'notifications_unread');
    case 'write': {
      const created = request('POST', '/api/v1/documents/', 'document_create', token,
        documentBody(`Loadtest ${runID}`), [201], phase);
      const data = json(created);
      if (!data || !data.id) return created;
      const updated = request('PUT', `/api/v1/documents/${data.id}`, 'document_update', token,
        documentBody(`Loadtest ${runID} updated`), [200], phase);
      request('DELETE', `/api/v1/documents/${data.id}`, 'document_delete', token, null, [204], phase);
      return updated;
    }
    case 'upload': {
      const uploaded = request('POST', '/api/v1/files/upload', 'file_upload', token,
        { file: http.file(content, `loadtest-${runID}.txt`, 'text/plain') }, [201], phase);
      const data = json(uploaded);
      if (!data || !data.file || !data.file.id) return uploaded;
      const download = get(`/api/v1/files/${data.file.id}/download`, 'file_download');
      const link = json(download);
      if (download.status === 200 && link && /^https:\/\//.test(link.url)) {
        const bytes = request('GET', link.url, 'file_content', null, null, [200], phase, true);
        const valid = check(bytes, { 'file_content: exact bytes': (r) => r.body === content }, { endpoint: 'file_content', phase });
        if (phase === 'preflight' && !valid) throw new Error('Preflight file content mismatch');
      } else {
        check(false, { 'file_download: HTTPS signed URL': (value) => value }, { phase });
        if (phase === 'preflight') throw new Error('Preflight download URL missing');
      }
      request('DELETE', `/api/v1/files/${data.file.id}`, 'file_delete', token, null, [204], phase);
      return download;
    }
    default: throw new Error(`Unknown action: ${action}`);
  }
}

export function setup() {
  const users = registerUsers();
  for (const user of users) {
    for (let i = 0; i < 3; i++) {
      const data = requireJSON(request('POST', '/api/v1/documents/', 'document_create', user.token,
        documentBody(`Loadtest ${runID} seed ${i}`), [201], 'setup'), 'id');
      user.documents.push(data.id);
      sleep(0.05);
    }
  }
  for (const action of [...new Set(plan)]) {
    const response = journey(action, users[0], 'preflight');
    if (!response || response.status < 200 || response.status >= 300) {
      throw new Error(`Preflight ${action} failed: status ${response && response.status}`);
    }
    console.log(`Preflight ${action}: HTTP ${response.status}`);
    sleep(0.1);
  }
  return { users };
}

export function iteration(data) {
  const user = data.users[(exec.vu.idInTest - 1) % data.users.length];
  journey(plan[exec.scenario.iterationInTest % plan.length], user);
  if (profile === 'smoke') sleep(0.5);
  else if (!['baseline', 'peak'].includes(profile)) sleep(1 + Math.random() * 2);
}

export function handleSummary(data) {
  const rows = Object.entries(data.metrics).filter(([, metric]) => metric.thresholds).sort(([a], [b]) => a.localeCompare(b))
    .map(([name, metric]) => {
      const failed = Object.entries(metric.thresholds).filter(([, result]) => !result.ok).map(([slo]) => slo);
      return `| ${name} | ${failed.length ? `FAIL: ${failed.join(', ')}` : 'PASS'} | ${JSON.stringify(metric.values)} |`;
    });
  const summary = `# Load test: ${profile}\n\nTarget: ${baseURL}\nRun: ${runID}\n\n` +
    '| Metric | SLO | Values (duration in ms) |\n|---|---|---|\n' + rows.join('\n') + '\n';
  const prefix = `tests/load/k6/results/${profile}-${runID}`;
  return {
    [`${prefix}.json`]: JSON.stringify({ profile, baseURL, runID, metrics: data.metrics, state: data.state }, null, 2),
    [`${prefix}.md`]: summary,
    stdout: summary,
  };
}
