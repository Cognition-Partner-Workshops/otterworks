import http from 'node:http';
import { readFile, writeFile, mkdir, rename } from 'node:fs/promises';
import { randomUUID, createHash, timingSafeEqual } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

export const users = [
  { id: 'commander', name: 'Incident Commander', initials: 'IC', color: '#8353a0' },
  { id: 'dba', name: 'DBA', initials: 'DB', color: '#287f86' },
  { id: 'sre', name: 'SRE', initials: 'SR', color: '#b66d29' },
  { id: 'alertmanager', name: 'Alertmanager', initials: 'AM', color: '#ce593b', bot: true },
  { id: 'devin', name: 'Devin', initials: 'D', color: '#3159b7', bot: true },
];
const channels = ['alerts', 'incident-war-room', 'platform'];
const root = path.dirname(fileURLToPath(import.meta.url));
const sessionId = value => typeof value === 'string' && /^(devin-)?[a-f0-9]{32}$/.test(value);
const sameSession = (a, b) => a.replace(/^devin-/, '') === b.replace(/^devin-/, '');
const secretEqual = (a, b) => Boolean(a && b) && Buffer.byteLength(a) === Buffer.byteLength(b) && timingSafeEqual(Buffer.from(a), Buffer.from(b));

export function config(env = process.env) {
  const apiBase = env.DEVIN_API_BASE || 'https://api.devin.ai';
  const webBase = env.DEVIN_WEB_BASE || 'https://app.devin.ai';
  for (const value of [apiBase, webBase, env.DEVIN_AUTOMATION_URL, env.ALERT_BATCH_WEBHOOK_URL].filter(Boolean)) {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Invalid upstream URL');
    if (url.protocol !== 'https:' && !['localhost', '127.0.0.1'].includes(url.hostname)) throw new Error('Upstream URLs require HTTPS except on loopback');
  }
  const route = env.DEVIN_TRIGGER_ROUTE || 'session';
  if (!['session', 'webhook'].includes(route)) throw new Error('Invalid trigger route');
  const webhookAction = env.DEVIN_WEBHOOK_ACTION || 'start_session';
  if (!['start_session', 'message_session'].includes(webhookAction)) throw new Error('Invalid webhook action');
  return {
    apiBase: apiBase.replace(/\/$/, ''), webBase: webBase.replace(/\/$/, ''),
    key: env.MOCK_SLACK_DEVIN_API_KEY || '', org: env.DEVIN_ORG_ID || '',
    owner: env.DEVIN_CREATE_AS_USER_ID || '', route, webhookAction,
    webhook: env.DEVIN_AUTOMATION_URL || '', webhookSecret: env.DEVIN_WEBHOOK_SECRET || '',
    receiverSecret: env.ALERTMANAGER_RECEIVER_SECRET || '',
    batchWebhook: env.ALERT_BATCH_WEBHOOK_URL || '',
    batchSecret: env.ALERT_BATCH_WEBHOOK_SECRET || '',
    batchQuietMs: Number(env.ALERT_BATCH_QUIET_MS || 90000),
    batchRequiredAlerts: (env.ALERT_BATCH_REQUIRED_ALERTS || '').split(',').map(value => value.trim()).filter(Boolean),
    stateFile: env.STATE_FILE || path.join(root, '.data/state.json'),
    transcriptFile: env.DEVIN_TRANSCRIPT_FILE || '',
    maxAcu: Number(env.DEVIN_MAX_ACU || 5),
    pollMs: Number(env.POLL_INTERVAL_MS || 5000),
  };
}

export async function createApp(cfg = config()) {
  if (!Number.isInteger(cfg.maxAcu) || cfg.maxAcu < 1 || cfg.maxAcu > 100) throw new Error('DEVIN_MAX_ACU must be 1 to 100');
  if (!Number.isFinite(cfg.pollMs) || cfg.pollMs < 100) throw new Error('Invalid poll interval');
  if (!Number.isFinite(cfg.batchQuietMs) || cfg.batchQuietMs < 1) throw new Error('Invalid alert batch quiet window');
  await mkdir(path.dirname(cfg.stateFile), { recursive: true });
  let state;
  try { state = JSON.parse(await readFile(cfg.stateFile, 'utf8')); }
  catch (e) { if (e.code !== 'ENOENT') throw e; state = { threads: [], alerts: {} }; }
  state.webhookBindings ||= {};
  if (state.alertBatch?.status === 'sending') state.alertBatch.status = 'uncertain';
  const save = async () => {
    await writeFile(`${cfg.stateFile}.tmp`, JSON.stringify(state), { mode: 0o600 });
    await rename(`${cfg.stateFile}.tmp`, cfg.stateFile);
  };
  // Persist before remote writes. An interrupted write stays uncertain, never retried automatically.
  for (const t of state.threads) {
    if (t.status === 'sending') { t.status = 'uncertain'; t.error = 'Delivery interrupted. Check Devin before starting another thread.'; }
  }
  await save();
  let queue = Promise.resolve();
  const serial = fn => { const next = queue.then(fn); queue = next.catch(() => {}); return next; };
  const api = async (suffix, method = 'GET', body) => {
    if (!cfg.key || !cfg.org) throw new Error('Session API is not configured');
    const response = await fetch(`${cfg.apiBase}/v3/organizations/${encodeURIComponent(cfg.org)}/sessions${suffix}`, {
      method, headers: { Authorization: `Bearer ${cfg.key}`, 'Content-Type': 'application/json' },
      ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(20000), redirect: 'error',
    });
    if (!response.ok) throw new Error(`Devin API returned ${response.status}`);
    if (method === 'POST' && suffix.endsWith('/messages')) return;
    return response.json();
  };
  const add = (t, author, text, requestId) => {
    const m = { id: randomUUID(), author, text, requestId, at: Date.now(), delivered: false };
    t.messages.push(m); return m;
  };
  const safeUrl = id => `${cfg.webBase}/sessions/${id.replace(/^devin-/, '')}`;
  const deliver = async t => {
    if (t.readOnly) return;
    if (['uncertain', 'failed'].includes(t.status)) return;
    const threadWebhook = t.route ? t.route === 'webhook' && t.webhookAction === 'message_session' : cfg.route === 'webhook' && cfg.webhookAction === 'message_session';
    if (t.status === 'webhook-delivered' && !t.sessionId && !threadWebhook) return;
    const pending = t.messages.filter(m => m.author !== 'devin' && !m.delivered);
    if (!pending.length) return;
    if (!t.sessionId && !(threadWebhook && t.route) && !pending.some(m => m.author === 'alertmanager' || /@devin\b/i.test(m.text))) return;
    if ((threadWebhook || (!t.sessionId && cfg.route === 'webhook')) && cfg.webhook && cfg.webhookSecret) {
      const key = createHash('sha256').update(cfg.webhook).digest('hex');
      if ((t.webhookKey && t.webhookKey !== key) || (state.webhookBindings[key] && state.webhookBindings[key] !== t.id)) {
        t.status = 'blocked';
        t.error = 'This automation is bound to another thread or the configured automation changed. Use a dedicated automation and persistent state for each thread.';
        await save(); return;
      }
      if (threadWebhook) {
        state.webhookBindings[key] = t.id;
        t.webhookKey = key; t.route = 'webhook'; t.webhookAction = 'message_session';
      }
    }
    t.status = 'sending'; t.error = null; await save();
    try {
      const message = pending.map(m => `${users.find(u => u.id === m.author).name}: ${m.text}`).join('\n\n');
      if (t.sessionId && !threadWebhook) {
        await api(`/${t.sessionId}/messages`, 'POST', { message });
      } else if (threadWebhook || cfg.route === 'webhook') {
        if (!cfg.webhook || !cfg.webhookSecret) throw new Error('Automation webhook is not configured');
        const response = await fetch(cfg.webhook, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Webhook-Secret': cfg.webhookSecret },
          body: JSON.stringify({ message, channel: t.channel, thread_id: t.id }), redirect: 'error', signal: AbortSignal.timeout(20000) });
        if (!response.ok) throw new Error(`Automation returned ${response.status}`);
        const result = await response.json().catch(() => ({}));
        const id = result.session_id || result.devin_id;
        if (sessionId(id) && t.sessionId && !sameSession(t.sessionId, id)) throw new Error('Automation destination changed');
        if (sessionId(id)) { t.sessionId = id; t.sessionUrl = safeUrl(id); }
        t.route = 'webhook'; t.webhookAction ||= cfg.webhookAction;
      } else {
        const result = await api('', 'POST', { prompt: message, devin_mode: 'fusion', max_acu_limit: cfg.maxAcu,
          tags: ['bankir-1105', 'mock-slack'], ...(cfg.owner ? { create_as_user_id: cfg.owner } : {}) });
        if (!sessionId(result.session_id)) throw new Error('Session response has no valid ID');
        t.sessionId = result.session_id; t.sessionUrl = safeUrl(t.sessionId); t.route = 'session';
      }
      pending.forEach(m => { m.delivered = true; });
      t.status = t.sessionId ? 'connected' : 'webhook-delivered';
    } catch (e) {
      t.status = 'uncertain';
      t.error = 'Delivery was not confirmed. Check the upstream session or automation before starting another thread.';
      console.error('Upstream delivery not confirmed:', e.message.replaceAll(cfg.key || '\0', '[redacted]').replaceAll(cfg.webhookSecret || '\0', '[redacted]'));
    }
    await save();
  };
  const post = async ({ channel, threadId, author, text, requestId, localOnly = false }) => {
    if (!channels.includes(channel) || !users.some(u => u.id === author && u.id !== 'devin') || typeof text !== 'string' || !text.trim() || text.length > 12000 || typeof requestId !== 'string' || requestId.length > 100 || !requestId) {
      throw Object.assign(new Error('Choose a channel, author and message (up to 12000 characters).'), { status: 400 });
    }
    const existing = state.threads.find(t => t.messages.some(m => m.requestId === requestId));
    if (existing) return existing;
    let t = threadId ? state.threads.find(t => t.id === threadId && t.channel === channel) : null;
    if (threadId && !t) throw Object.assign(new Error('Thread not found'), { status: 404 });
    if (!t) { t = { id: randomUUID(), channel, messages: [], status: 'idle', ...(localOnly ? { readOnly: true } : {}) }; state.threads.push(t); }
    add(t, author, text.trim(), requestId); await save(); await deliver(t); return t;
  };
  let batchTimer;
  const batchComplete = batch => (cfg.batchRequiredAlerts || []).every(name =>
    batch.alerts.some(alert => alert.labels.alertname === name));
  const flushBatch = async () => {
    const batch = state.alertBatch;
    if (!batch || batch.status !== 'pending' || !cfg.batchWebhook || !batchComplete(batch)) return;
    batch.status = 'sending'; await save();
    const message = `Alert storm (${batch.alerts.length} alerts)\n\n` + batch.alerts.map(a =>
      `${a.labels.alertname || 'Alert'} | scenario: ${a.labels.scenario || '-'} | severity: ${a.labels.severity || '-'}\n${a.annotations?.summary || ''}\nstartsAt: ${a.startsAt || '-'}\nlabels: ${JSON.stringify(a.labels)}`).join('\n\n');
    let note;
    try {
      const response = await fetch(cfg.batchWebhook, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(cfg.batchSecret ? { Authorization: `Bearer ${cfg.batchSecret}` } : {}) },
        body: JSON.stringify({ message, channel: 'alerts', alerts: batch.alerts }), redirect: 'error', signal: AbortSignal.timeout(20000) });
      if (!response.ok) throw new Error('Batch delivery failed');
      const result = await response.json().catch(() => ({}));
      const id = result.session_id || result.devin_id;
      batch.status = 'delivered';
      note = `Handed ${batch.alerts.length} alerts to Devin.${sessionId(id) ? ` ${safeUrl(id)}` : ''}`;
    } catch {
      batch.status = 'uncertain';
      note = 'Alert batch delivery was not confirmed. Check the automation history before retrying.';
    }
    const thread = { id: randomUUID(), channel: 'alerts', messages: [], status: batch.status, readOnly: true };
    add(thread, 'devin', note); state.threads.push(thread); await save();
  };
  const scheduleBatch = () => {
    clearTimeout(batchTimer);
    if (cfg.batchWebhook && state.alertBatch?.status === 'pending' && batchComplete(state.alertBatch)) {
      batchTimer = setTimeout(() => serial(flushBatch).catch(() => {}), Math.max(0, state.alertBatch.lastAt + cfg.batchQuietMs - Date.now()));
      batchTimer.unref();
    }
  };
  scheduleBatch();
  const poll = () => serial(async () => {
    const mirrored = new Set();
    for (const t of state.threads) t.replyMirror = false;
    if (cfg.transcriptFile) {
      try {
        const mirror = JSON.parse(await readFile(cfg.transcriptFile, 'utf8'));
        if (!Array.isArray(mirror.items)) throw new Error('Invalid mirror');
        for (const item of mirror.items) {
          if (!item || !Array.isArray(item.messages)) continue;
          const t = state.threads.find(t => t.id === item.thread_id && t.route === 'webhook');
          if (!t || !sessionId(item.session_id) || (t.sessionId && !sameSession(t.sessionId, item.session_id))) continue;
          t.sessionId = item.session_id; t.sessionUrl = safeUrl(t.sessionId); t.replyMirror = true;
          mirrored.add(t.id);
          t.readOnly = t.webhookAction !== 'message_session';
          if (!['uncertain', 'failed', 'blocked'].includes(t.status)) t.status = t.readOnly ? 'Read mirror · follow-up messages stay local' : 'Read mirror · replies sent through webhook';
          for (const m of item.messages) {
            if (m && m.source === 'devin' && m.event_id && typeof m.message === 'string' && !t.messages.some(x => x.remoteId === m.event_id)) {
              t.messages.push({ id: randomUUID(), author: 'devin', text: m.message, remoteId: m.event_id, at: m.created_at * 1000, delivered: true });
            }
          }
        }
        state.mirrorError = null;
      } catch { state.mirrorError = 'Could not read the local transcript mirror; API-backed polling continues.'; }
    }
    for (const t of state.threads.filter(t => t.sessionId && !mirrored.has(t.id) && cfg.key && cfg.org)) {
      try {
        let cursor = t.cursor;
        // A bounded page loop prevents a long transcript from starving chat writes.
        for (let page = 0; page < 10; page++) {
          const data = await api(`/${t.sessionId}/messages?first=100${cursor ? `&after=${encodeURIComponent(cursor)}` : ''}`);
          for (const m of data.items || []) {
            if (m.source === 'devin' && typeof m.message === 'string' && !t.messages.some(x => x.remoteId === m.event_id)) {
              t.messages.push({ id: randomUUID(), author: 'devin', text: m.message, remoteId: m.event_id, at: m.created_at * 1000, delivered: true });
            }
          }
          if (data.end_cursor) { cursor = data.end_cursor; t.cursor = cursor; }
          if (!data.has_next_page) break;
        }
        t.pollError = null;
        if (t.status.startsWith('Read mirror')) t.status = t.readOnly ? 'API replies · follow-up messages stay local' : 'connected';
      } catch { t.pollError = 'Could not refresh Devin replies; polling will retry.'; }
    }
    await save();
  });
  const json = (res, status, value) => { res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(value)); };
  const body = async req => {
    let value = ''; for await (const chunk of req) { value += chunk; if (value.length > 65536) throw Object.assign(new Error('Request too large'), { status: 413 }); }
    try { return JSON.parse(value); } catch { throw Object.assign(new Error('Invalid JSON'), { status: 400 }); }
  };
  const server = http.createServer(async (req, res) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'");
    try {
      const url = new URL(req.url, 'http://localhost');
      if (req.method === 'GET' && url.pathname === '/healthz') return json(res, 200, { ok: true });
      if (req.method === 'POST' && url.pathname === '/receivers/alertmanager') {
        if (!secretEqual(req.headers['x-webhook-secret'] || '', cfg.receiverSecret)) return json(res, 401, { error: 'Receiver authentication required' });
        const data = await body(req);
        const alerts = data.alerts;
        if (!Array.isArray(alerts) || alerts.length > 100) return json(res, 400, { error: 'Expected an Alertmanager webhook with alerts' });
        return json(res, 200, await serial(async () => {
          const ids = [];
          for (const alert of alerts) {
            if (!alert.labels || typeof alert.labels !== 'object') continue;
            const key = createHash('sha256').update(JSON.stringify([alert.fingerprint || alert.labels, alert.startsAt])).digest('hex');
            if (state.alerts[key] || (alert.status || data.status) === 'resolved') continue;
            const t = await post({ channel: 'alerts', author: 'alertmanager', text: `${alert.labels.alertname || 'Alert'} (${alert.status || data.status || 'firing'})\n${alert.annotations?.summary || ''}\n${JSON.stringify(alert.labels)}`,
              requestId: `alert-${key}`, localOnly: Boolean(cfg.batchWebhook) });
            state.alerts[key] = t.id; ids.push(t.id);
            if (cfg.batchWebhook) {
              if (state.alertBatch?.status !== 'pending') state.alertBatch = { alerts: [], status: 'pending' };
              state.alertBatch.alerts.push(alert); state.alertBatch.lastAt = Date.now();
            }
          }
          await save(); if (ids.length) scheduleBatch(); return { threadIds: ids };
        }));
      }
      // The browser sends JSON plus a custom header; cross-origin forms cannot submit chat writes.
      if (req.method === 'POST' && (!req.headers['content-type']?.startsWith('application/json') || req.headers['x-workspace-client'] !== 'mock-slack' || (req.headers.origin && req.headers.origin !== `http://${req.headers.host}` && req.headers.origin !== `https://${req.headers.host}`))) return json(res, 403, { error: 'Same-origin workspace request required' });
      if (req.method === 'GET' && url.pathname === '/api/state') return json(res, 200, { users, channels, threads: state.threads, mirrorError: cfg.transcriptFile ? state.mirrorError || null : null, configured: cfg.route === 'webhook' ? Boolean(cfg.webhook && cfg.webhookSecret) : Boolean(cfg.key && cfg.org), route: cfg.route });
      if (req.method === 'POST' && url.pathname === '/api/messages') return json(res, 200, await serial(async () => post(await body(req))));
      const files = { '/': ['index.html', 'text/html'], '/app.js': ['app.js', 'text/javascript'], '/style.css': ['style.css', 'text/css'] };
      if (req.method === 'GET' && files[url.pathname]) {
        const [file, type] = files[url.pathname]; res.writeHead(200, { 'Content-Type': type }); return res.end(await readFile(path.join(root, 'public', file)));
      }
      json(res, 404, { error: 'Not found' });
    } catch (e) { json(res, e.status || 500, { error: e.status ? e.message : 'Workspace request failed' }); }
  });
  let polling = false;
  const timer = setInterval(() => { if (!polling) { polling = true; poll().catch(() => {}).finally(() => { polling = false; }); } }, cfg.pollMs);
  timer.unref();
  server.on('close', () => { clearInterval(timer); clearTimeout(batchTimer); });
  return { server, poll };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const { server } = await createApp();
  server.listen(Number(process.env.PORT || 3100), process.env.HOST || '127.0.0.1', () => console.log('Mock Slack ready'));
  for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => server.close(() => process.exit(0)));
}
