import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { createApp, config } from './server.mjs';

const ID = 'devin-0123456789abcdef0123456789abcdef';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function fixture(t, { route = 'session', fail = false, noSession = false, emptyMessage = false, webhookAction = 'start_session', alternateIds = false, batch = false } = {}) {
  const calls = [];
  const upstream = http.createServer(async (req, res) => {
    let body = ''; for await (const b of req) body += b;
    calls.push({ url: req.url, method: req.method, body: body ? JSON.parse(body) : null, auth: req.headers.authorization, secret: req.headers['x-webhook-secret'] });
    res.setHeader('Content-Type', 'application/json');
    if (fail) { res.writeHead(503); res.end('{}'); return; }
    if (emptyMessage && req.method === 'POST' && req.url.endsWith('/messages')) { res.writeHead(204); res.end(); return; }
    if (req.method === 'POST') { res.end(JSON.stringify(noSession ? { ok: true } : { session_id: alternateIds && calls.length % 2 === 0 ? ID.replace(/^devin-/, '') : ID })); return; }
    const after = new URL(req.url, 'http://localhost').searchParams.get('after');
    res.end(JSON.stringify({ items: [{ event_id: 'event-1', source: 'devin', message: 'DBA, I will check the query plan.', created_at: 1 }], has_next_page: !after, end_cursor: after ? null : 'cursor-1' }));
  });
  await new Promise(r => upstream.listen(0, '127.0.0.1', r));
  const dir = await mkdtemp(path.join(os.tmpdir(), 'collection-test-'));
  const base = `http://127.0.0.1:${upstream.address().port}`;
  const cfg = config({ DEVIN_API_BASE: base, DEVIN_WEB_BASE: 'http://localhost:4000', MOCK_SLACK_DEVIN_API_KEY: 'fixture-key', DEVIN_ORG_ID: 'org-fixture', DEVIN_CREATE_AS_USER_ID: 'user-persona', STATE_FILE: path.join(dir, 'state.json'), DEVIN_TRIGGER_ROUTE: route, DEVIN_WEBHOOK_ACTION: webhookAction, DEVIN_AUTOMATION_URL: `${base}/hook`, DEVIN_WEBHOOK_SECRET: 'fixture-webhook-secret', ALERTMANAGER_RECEIVER_SECRET: 'fixture-receiver-secret', POLL_INTERVAL_MS: '600000' });
  if (batch) { cfg.batchWebhook = `${base}/batch`; cfg.batchSecret = 'batch-secret'; cfg.batchQuietMs = 80; }
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

test('alert batches wait for quiet, include every new firing alert and do not bind threads', async t => {
  const f = await fixture(t, { batch: true });
  const alerts = ['n-plus-one', 'cache-leak', 'log-flood', 'double-run'].map(scenario => ({
    status: 'firing', fingerprint: scenario, startsAt: '2026-11-05T00:00:00Z',
    labels: { alertname: `Alert-${scenario}`, scenario, severity: 'critical' }, annotations: { summary: `Summary ${scenario}` },
  }));
  const send = items => fetch(`${f.url}/receivers/alertmanager`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Webhook-Secret': 'fixture-receiver-secret' }, body: JSON.stringify({ alerts: items }) });
  await send([]); await pause(100); assert.equal(f.calls.length, 0);
  await send(alerts.slice(0, 2)); await pause(40); assert.equal(f.calls.length, 0);
  await send(alerts); await send([{ ...alerts[0], fingerprint: 'resolved', status: 'resolved' }]);
  await pause(160);
  assert.equal(f.calls.length, 1); assert.equal(f.calls[0].url, '/batch');
  assert.equal(f.calls[0].auth, 'Bearer batch-secret');
  assert.equal(f.calls[0].secret, undefined);
  assert.deepEqual(f.calls[0].body.alerts, alerts);
  for (const a of alerts) for (const text of [a.labels.alertname, a.labels.scenario, a.labels.severity, a.annotations.summary, a.startsAt, JSON.stringify(a.labels)]) assert.ok(f.calls[0].body.message.includes(text));
  const state = await (await fetch(`${f.url}/api/state`)).json();
  assert.equal(state.threads.length, 5); assert.match(state.threads[4].messages[0].text, /Handed 4 alerts to Devin.*sessions\//);
  assert.ok(!JSON.stringify(state).includes('batch-secret'));
  await send(alerts); await pause(120); assert.equal(f.calls.length, 1);
});
test('failed batch is visible and is not automatically retried', async t => {
  const f = await fixture(t, { batch: true, fail: true });
  await fetch(`${f.url}/receivers/alertmanager`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Webhook-Secret': 'fixture-receiver-secret' }, body: JSON.stringify({ alerts: [{ labels: { alertname: 'Failure' }, startsAt: 'now' }] }) });
  await pause(180);
  const state = await (await fetch(`${f.url}/api/state`)).json();
  assert.match(state.threads.at(-1).messages[0].text, /not confirmed/);
  assert.equal(f.calls.length, 1);
});
test('required alert names hold a partial batch beyond quiet until every page arrives', async t => {
  const f = await fixture(t, { batch: true });
  f.cfg.batchRequiredAlerts = ['First', 'Last'];
  const send = name => fetch(`${f.url}/receivers/alertmanager`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Webhook-Secret': 'fixture-receiver-secret' }, body: JSON.stringify({ alerts: [{ status: 'firing', labels: { alertname: name }, startsAt: 'now' }] }) });
  await send('First'); await pause(160);
  assert.equal(f.calls.length, 0);
  await send('Last'); await pause(30);
  assert.equal(f.calls.length, 0);
  await pause(130);
  assert.equal(f.calls.length, 1);
  assert.deepEqual(f.calls[0].body.alerts.map(alert => alert.labels.alertname), ['First', 'Last']);
});
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
test('webhook configuration works without a session API credential', async t => {
  const f = await fixture(t, { route: 'webhook', noSession: true }); f.cfg.key = '';
  const state = await (await fetch(`${f.url}/api/state`)).json();
  assert.equal(state.configured, true);
  assert.equal((await f.post('@devin Check latency')).status, 'webhook-delivered');
});
test('message_session webhook forwards three named authors without a write key or returned ID', async t => {
  const f = await fixture(t, { route: 'webhook', webhookAction: 'message_session', noSession: true }); f.cfg.key = '';
  const first = await f.post('@devin Check latency');
  await f.post('Check query fan-out.', first.id, 'dba-turn', 'dba');
  await f.post('Traffic is unchanged.', first.id, 'sre-turn', 'sre');
  await f.post('Traffic is unchanged.', first.id, 'sre-turn', 'sre');
  assert.equal(f.calls.length, 3);
  assert.ok(f.calls.every(c => c.url === '/hook' && c.body.thread_id === first.id && !c.auth));
  assert.deepEqual(f.calls.map(c => c.body.message), ['Incident Commander: @devin Check latency', 'DBA: Check query fan-out.', 'SRE: Traffic is unchanged.']);
});
test('message_session stays on its webhook even after a destination ID is known', async t => {
  const f = await fixture(t, { route: 'webhook', webhookAction: 'message_session' });
  const first = await f.post('@devin Check latency');
  await f.post('Keep the same destination.', first.id);
  assert.equal(f.calls.length, 2); assert.ok(f.calls.every(c => c.url === '/hook'));
});
test('message_session binding survives restart and blocks a second thread', async t => {
  const f = await fixture(t, { route: 'webhook', webhookAction: 'message_session', noSession: true });
  const first = await f.post('@devin Check latency');
  const second = await createApp(f.cfg); await new Promise(r => second.server.listen(0, '127.0.0.1', r));
  t.after(() => new Promise(r => second.server.close(r)));
  const post = async (text, threadId) => (await fetch(`http://127.0.0.1:${second.server.address().port}/api/messages`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workspace-Client': 'mock-slack' }, body: JSON.stringify({ channel: 'incident-war-room', author: 'dba', text, threadId, requestId: crypto.randomUUID() }) })).json();
  const blocked = await post('@devin Another incident');
  assert.equal(blocked.status, 'blocked'); assert.match(blocked.error, /bound to another thread/); assert.equal(f.calls.length, 1);
  await post('Resume after restart.', first.id);
  assert.equal(f.calls.length, 2); assert.equal(f.calls[1].body.thread_id, first.id);
});
test('message_session cannot silently switch its automation URL', async t => {
  const f = await fixture(t, { route: 'webhook', webhookAction: 'message_session', noSession: true });
  const first = await f.post('@devin Check latency'); f.cfg.webhook += '-replacement';
  const blocked = await f.post('Continue in the original session.', first.id);
  assert.equal(blocked.status, 'blocked'); assert.equal(f.calls.length, 1);
});
test('changing webhook action after restart never bypasses a claimed destination', async t => {
  const f = await fixture(t, { route: 'webhook', webhookAction: 'message_session', noSession: true });
  await f.post('@devin Check latency'); f.cfg.webhookAction = 'start_session';
  const second = await createApp(f.cfg); await new Promise(r => second.server.listen(0, '127.0.0.1', r));
  t.after(() => new Promise(r => second.server.close(r)));
  const response = await fetch(`http://127.0.0.1:${second.server.address().port}/api/messages`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workspace-Client': 'mock-slack' }, body: JSON.stringify({ channel: 'platform', author: 'sre', text: '@devin Separate incident', requestId: 'other-incident' }) });
  assert.equal((await response.json()).status, 'blocked'); assert.equal(f.calls.length, 1);
});
test('equivalent prefixed and bare destination IDs allow webhook and mirror updates', async t => {
  const f = await fixture(t, { route: 'webhook', webhookAction: 'message_session', alternateIds: true });
  const first = await f.post('@devin Check latency'); f.cfg.transcriptFile = path.join(f.dir, 'mirror.json');
  await writeFile(f.cfg.transcriptFile, JSON.stringify({ items: [{ thread_id: first.id, session_id: ID.replace(/^devin-/, ''), messages: [] }] }));
  await f.app.poll();
  const updated = await f.post('Same destination.', first.id);
  assert.equal(updated.replyMirror, true); assert.equal(updated.status, 'connected'); assert.equal(updated.messages.at(-1).delivered, true);
  assert.equal(f.calls.length, 2);
});
for (const webhookAction of ['start_session', 'message_session']) test(`${webhookAction} falls back to API reads when mirror coverage disappears`, async t => {
  const f = await fixture(t, { route: 'webhook', webhookAction }); const first = await f.post('@devin Check latency');
  f.cfg.transcriptFile = path.join(f.dir, 'mirror.json');
  await writeFile(f.cfg.transcriptFile, JSON.stringify({ items: [{ thread_id: first.id, session_id: ID, messages: [] }] }));
  await f.app.poll(); assert.equal(f.calls.length, 1);
  await rm(f.cfg.transcriptFile); await f.app.poll();
  assert.ok(f.calls.some(c => c.method === 'GET'));
  let state = await (await fetch(`${f.url}/api/state`)).json();
  assert.equal(state.threads[0].replyMirror, false);
  assert.equal(state.threads[0].messages.filter(m => m.author === 'devin').length, 1); assert.ok(state.mirrorError);
  await writeFile(f.cfg.transcriptFile, '{"items":[]}'); await f.app.poll();
  state = await (await fetch(`${f.url}/api/state`)).json(); assert.equal(state.mirrorError, null);
  assert.equal(state.threads[0].replyMirror, false);
});
test('message_session reply mirror remains readable while follow-ups use the webhook', async t => {
  const f = await fixture(t, { route: 'webhook', webhookAction: 'message_session', noSession: true }); f.cfg.key = '';
  const first = await f.post('@devin Check latency'); f.cfg.transcriptFile = path.join(f.dir, 'mirror.json');
  await writeFile(f.cfg.transcriptFile, JSON.stringify({ items: [{ thread_id: first.id, session_id: ID, messages: [{ event_id: 'first-reply', source: 'devin', message: 'Actual read-backed reply', created_at: 1 }] }] }));
  await f.app.poll(); await f.app.poll();
  const next = await f.post('Check the index next.', first.id, 'sre-turn', 'sre');
  assert.equal(next.readOnly, false); assert.equal(next.replyMirror, true);
  assert.equal(next.messages.filter(m => m.author === 'devin').length, 1);
  assert.equal(f.calls.length, 2); assert.ok(f.calls.every(c => c.url === '/hook'));
  assert.equal(next.messages.at(-1).delivered, true);
});
test('empty successful message response confirms delivery', async t => {
  const f = await fixture(t, { emptyMessage: true }); const first = await f.post('@devin Check latency');
  const updated = await f.post('Database is healthy', first.id);
  assert.equal(updated.status, 'connected'); assert.equal(updated.messages.at(-1).delivered, true);
});
test('read mirror attaches one verified webhook session without API writes', async t => {
  const f = await fixture(t, { route: 'webhook', noSession: true }); f.cfg.key = '';
  const first = await f.post('@devin Check latency');
  f.cfg.transcriptFile = path.join(f.dir, 'mirror.json');
  await writeFile(f.cfg.transcriptFile, JSON.stringify({ items: [{ thread_id: first.id, session_id: ID, messages: [{ event_id: 'read-event', source: 'devin', message: 'Actual read-only transcript', created_at: 1 }] }] }));
  await f.app.poll(); await f.app.poll(); await f.post('Follow-up stays local', first.id);
  const state = await (await fetch(`${f.url}/api/state`)).json();
  assert.equal(state.threads[0].readOnly, true);
  assert.equal(state.threads[0].messages.filter(m => m.author === 'devin').length, 1);
  assert.equal(f.calls.length, 1);
});
test('missing or invalid optional mirror never blocks API-backed replies', async t => {
  const f = await fixture(t); await f.post('@devin Check latency');
  f.cfg.transcriptFile = path.join(f.dir, 'mirror.json');
  await f.app.poll();
  let state = await (await fetch(`${f.url}/api/state`)).json();
  assert.equal(state.threads[0].messages.filter(m => m.author === 'devin').length, 1);
  assert.match(state.mirrorError, /API-backed polling continues/);
  await writeFile(f.cfg.transcriptFile, '{invalid'); await f.app.poll();
  state = await (await fetch(`${f.url}/api/state`)).json(); assert.ok(state.mirrorError);
  f.cfg.transcriptFile = '';
  state = await (await fetch(`${f.url}/api/state`)).json(); assert.equal(state.mirrorError, null);
  f.cfg.transcriptFile = path.join(f.dir, 'mirror.json');
  await writeFile(f.cfg.transcriptFile, '{"items":[]}'); await f.app.poll();
  state = await (await fetch(`${f.url}/api/state`)).json(); assert.equal(state.mirrorError, null);
});
test('browser retains one request ID after a lost response and page reload', async () => {
  const source = await readFile(new URL('./public/app.js', import.meta.url), 'utf8');
  const storage = new Map(); const sent = [];
  let fail = true;
  const boot = () => {
    const nodes = { author: { value: 'commander' }, error: {}, message: { id: 'message', value: '@devin Check latency' } };
    const context = { document: { getElementById: id => nodes[id] }, crypto,
      sessionStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
      fetch: async (_url, options) => { sent.push(JSON.parse(options.body)); if (fail) throw new Error('Response lost'); return { ok: true, json: async () => ({ id: 'thread-original' }) }; }
    };
    vm.runInNewContext(source.slice(0, source.indexOf("$('compose').onsubmit")) + '\nglobalThis.send = send; refresh = async () => {};', context);
    return { context, nodes };
  };
  const first = boot(); await first.context.send(first.nodes.message, null);
  assert.ok(storage.has('pending-message'));
  const second = boot(); second.nodes.message.value = 'Different message'; await second.context.send(second.nodes.message, null);
  assert.equal(sent.length, 1);
  second.nodes.message.value = '@devin Check latency'; fail = false; await second.context.send(second.nodes.message, null);
  assert.equal(sent.length, 2); assert.equal(sent[0].requestId, sent[1].requestId); assert.equal(storage.has('pending-message'), false);
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
