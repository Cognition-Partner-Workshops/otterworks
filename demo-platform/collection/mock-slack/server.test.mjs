import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createApp, config } from './server.mjs';

const ID = 'devin-0123456789abcdef0123456789abcdef';
async function fixture(t, { route = 'session', fail = false, noSession = false } = {}) {
  const calls = [];
  const upstream = http.createServer(async (req, res) => {
    let body = ''; for await (const b of req) body += b;
    calls.push({ url: req.url, method: req.method, body: body ? JSON.parse(body) : null, auth: req.headers.authorization, secret: req.headers['x-webhook-secret'] });
    res.setHeader('Content-Type', 'application/json');
    if (fail) { res.writeHead(503); res.end('{}'); return; }
    if (req.method === 'POST') { res.end(JSON.stringify(noSession ? { ok: true } : { session_id: ID })); return; }
    const after = new URL(req.url, 'http://localhost').searchParams.get('after');
    res.end(JSON.stringify({ items: [{ event_id: 'event-1', source: 'devin', message: 'DBA, I will check the query plan.', created_at: 1 }], has_next_page: !after, end_cursor: after ? null : 'cursor-1' }));
  });
  await new Promise(r => upstream.listen(0, '127.0.0.1', r));
  const dir = await mkdtemp(path.join(os.tmpdir(), 'collection-test-'));
  const base = `http://127.0.0.1:${upstream.address().port}`;
  const cfg = config({ DEVIN_API_BASE: base, DEVIN_WEB_BASE: 'http://localhost:4000', MOCK_SLACK_DEVIN_API_KEY: 'fixture-key', DEVIN_ORG_ID: 'org-fixture', DEVIN_CREATE_AS_USER_ID: 'user-persona', STATE_FILE: path.join(dir, 'state.json'), DEVIN_TRIGGER_ROUTE: route, DEVIN_AUTOMATION_URL: `${base}/hook`, DEVIN_WEBHOOK_SECRET: 'fixture-webhook-secret', ALERTMANAGER_RECEIVER_SECRET: 'fixture-receiver-secret', POLL_INTERVAL_MS: '600000' });
  const app = await createApp(cfg);
  await new Promise(r => app.server.listen(0, '127.0.0.1', r));
  const url = `http://127.0.0.1:${app.server.address().port}`;
  t.after(async () => { await new Promise(r => app.server.close(r)); await new Promise(r => upstream.close(r)); await rm(dir, { recursive: true, force: true }); });
  const post = async (text, threadId, requestId = crypto.randomUUID(), author = 'commander') => {
    const r = await fetch(`${url}/api/messages`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workspace-Client': 'mock-slack' }, body: JSON.stringify({ channel: 'incident-war-room', author, text, threadId, requestId }) });
    assert.equal(r.status, 200); return r.json();
  };
  return { app, cfg, calls, dir, url, post };
}

test('named people reach one Fusion session, polling deduplicates replies across pages', async t => {
  const f = await fixture(t);
  const first = await f.post('@devin Please check the document list.');
  await Promise.all([f.post('Check query fan-out first.', first.id, 'dba-message', 'dba'), f.post('Traffic is unchanged.', first.id, 'sre-message', 'sre')]);
  assert.equal(f.calls.filter(c => c.method === 'POST' && c.url.endsWith('/sessions')).length, 1);
  assert.deepEqual(f.calls[0].body, { prompt: 'Incident Commander: @devin Please check the document list.', devin_mode: 'fusion', max_acu_limit: 5, tags: ['bankir-1105', 'mock-slack'], create_as_user_id: 'user-persona' });
  assert.equal(f.calls[1].body.message, 'DBA: Check query fan-out first.');
  assert.equal(f.calls[2].body.message, 'SRE: Traffic is unchanged.');
  await f.app.poll(); await f.app.poll();
  const state = await (await fetch(`${f.url}/api/state`)).json();
  assert.equal(state.threads[0].messages.filter(m => m.author === 'devin').length, 1);
  assert.ok(f.calls.some(c => c.url.includes('after=cursor-1')));
  assert.ok(!JSON.stringify(state).includes('fixture-key'));
  assert.ok(!JSON.stringify(state).includes('fixture-webhook-secret'));
});
test('repeated client request does not send a duplicate POST', async t => {
  const f = await fixture(t);
  await f.post('@devin Check latency', null, 'one-request');
  await f.post('@devin Check latency', null, 'one-request');
  assert.equal(f.calls.length, 1);
});
test('a passive thread starts only when mentioned, carrying the preceding context', async t => {
  const f = await fixture(t);
  const first = await f.post('Document uploads are slow'); assert.equal(f.calls.length, 0);
  await f.post('@devin Please investigate', first.id, 'mention', 'dba');
  assert.equal(f.calls.length, 1);
  assert.match(f.calls[0].body.prompt, /Incident Commander: Document uploads are slow\n\nDBA:/);
});
test('restart retains mapping and reply cursor', async t => {
  const f = await fixture(t); const first = await f.post('@devin Check latency'); await f.app.poll();
  const second = await createApp(f.cfg); await new Promise(r => second.server.listen(0, '127.0.0.1', r));
  t.after(() => new Promise(r => second.server.close(r)));
  const base = `http://127.0.0.1:${second.server.address().port}`;
  const r = await fetch(`${base}/api/messages`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workspace-Client': 'mock-slack' }, body: JSON.stringify({ channel: 'incident-war-room', author: 'dba', text: 'Resume the same thread', threadId: first.id, requestId: 'resume' }) });
  assert.equal(r.status, 200);
  assert.equal(f.calls.filter(c => c.method === 'POST' && c.url.endsWith('/sessions')).length, 1);
  assert.ok(f.calls.at(-1).url.includes(`/${ID}/messages`));
});
test('uncertain delivery is visible and never retried on another reply', async t => {
  const f = await fixture(t, { fail: true });
  const first = await f.post('@devin Check latency'); assert.equal(first.status, 'uncertain');
  await f.post('More context', first.id); assert.equal(f.calls.length, 1);
});
test('interrupted writes remain uncertain after restart', async t => {
  const f = await fixture(t); await f.post('@devin Check latency');
  const persisted = JSON.parse(await readFile(f.cfg.stateFile, 'utf8')); persisted.threads[0].status = 'sending';
  const { writeFile } = await import('node:fs/promises'); await writeFile(f.cfg.stateFile, JSON.stringify(persisted));
  const second = await createApp(f.cfg); await new Promise(r => second.server.listen(0, '127.0.0.1', r)); t.after(() => new Promise(r => second.server.close(r)));
  const state = await (await fetch(`http://127.0.0.1:${second.server.address().port}/api/state`)).json();
  assert.equal(state.threads[0].status, 'uncertain');
});
test('webhook route sends the shared secret server-side instead of creating a session', async t => {
  const f = await fixture(t, { route: 'webhook' });
  const first = await f.post('@devin Check latency');
  assert.equal(f.calls[0].url, '/hook'); assert.equal(f.calls[0].secret, 'fixture-webhook-secret');
  await f.post('More context', first.id, 'follow-up', 'dba'); assert.ok(f.calls[1].url.includes(`/${ID}/messages`));
});
test('webhook without a returned session ID never starts duplicate work', async t => {
  const f = await fixture(t, { route: 'webhook', noSession: true }); const first = await f.post('@devin Check latency');
  await f.post('More context', first.id); assert.equal(f.calls.length, 1);
});
test('Alertmanager receiver authenticates, deduplicates repeats, ignores resolved', async t => {
  const f = await fixture(t);
  const payload = { status: 'firing', alerts: [{ status: 'firing', startsAt: '2026-11-05T00:00:00Z', fingerprint: 'fanout', labels: { alertname: 'DocumentListLatencyHigh' }, annotations: { summary: 'Document list p95 is high' } }] };
  const receiver = secret => fetch(`${f.url}/receivers/alertmanager`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Webhook-Secret': secret }, body: JSON.stringify(payload) });
  assert.equal((await receiver('bad')).status, 401);
  assert.equal((await receiver('fixture-receiver-secret')).status, 200);
  await receiver('fixture-receiver-secret');
  payload.alerts[0].status = 'resolved'; await receiver('fixture-receiver-secret');
  assert.equal(f.calls.length, 1); assert.match(f.calls[0].body.prompt, /^Alertmanager:/);
});
test('browser writes reject cross origin and invalid authors, paths cannot escape public files', async t => {
  const f = await fixture(t);
  const r = await fetch(`${f.url}/api/messages`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workspace-Client': 'mock-slack', Origin: 'https://attacker.invalid' }, body: '{}' }); assert.equal(r.status, 403);
  const invalid = await fetch(`${f.url}/api/messages`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workspace-Client': 'mock-slack' }, body: JSON.stringify({ channel: 'alerts', author: 'devin', text: 'Forged reply', requestId: 'invalid' }) }); assert.equal(invalid.status, 400);
  assert.equal((await fetch(`${f.url}/server.mjs`)).status, 404);
  assert.equal((await fetch(`${f.url}/.data/state.json`)).status, 404);
});
test('configuration rejects non-loopback plaintext credentials and bad ACU limits', async () => {
  assert.throws(() => config({ DEVIN_API_BASE: 'http://upstream.invalid' }));
  await assert.rejects(createApp({ ...config(), maxAcu: NaN }));
});
