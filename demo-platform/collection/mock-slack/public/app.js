let snapshot = { users: [], channels: [], threads: [] };
let channel = 'incident-war-room';
let threadId = null;
let sending = false;
let pending = JSON.parse(sessionStorage.getItem('pending-message') || 'null');
const $ = id => document.getElementById(id);
const el = (tag, cls, value) => { const n = document.createElement(tag); if (cls) n.className = cls; if (value) n.textContent = value; return n; };
function message(m) {
  const user = snapshot.users.find(u => u.id === m.author);
  const item = el('article', 'message');
  const avatar = el('span', `avatar avatar-${m.author}`, user.initials);
  const content = el('div', 'message-content');
  const byline = el('div', 'byline');
  byline.append(el('strong', '', user.name));
  if (user.bot) byline.append(el('span', 'bot-badge', 'APP'));
  byline.append(el('time', '', new Date(m.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })));
  content.append(byline, el('p', 'message-text', m.text)); item.append(avatar, content); return item;
}
function render() {
  $('run-token').textContent = snapshot.runToken || 'collection';
  $('channels').replaceChildren(...snapshot.channels.map(name => {
    const b = el('button', name === channel ? 'channel selected' : 'channel', `#  ${name}`);
    b.onclick = () => { channel = name; threadId = null; render(); }; return b;
  }));
  $('people').replaceChildren(...snapshot.users.map(u => { const row = el('div', 'person'); row.append(el('span', `small-avatar avatar-${u.id}`, u.initials), el('span', '', u.name)); return row; }));
  $('channel-title').textContent = `# ${channel}`;
  $('message').placeholder = `Message #${channel}. Mention @devin to start work.`;
  $('connection').textContent = snapshot.configured ? `Devin connected · ${snapshot.route === 'webhook' ? 'Automation trigger' : 'Fusion sessions'} · credentials stay on the server` : `Local workspace · configure ${snapshot.route === 'webhook' ? 'an automation webhook' : 'a persona-owned API key'} to connect Devin`;
  if (snapshot.mirrorError) $('connection').textContent += ` · ${snapshot.mirrorError}`;
  const threads = snapshot.threads.filter(t => t.channel === channel);
  $('messages').replaceChildren(...threads.map(t => {
    const row = el('div', 'channel-message'); row.append(message(t.messages[0]));
    const open = el('button', 'open-thread', `${t.messages.length - 1} replies${t.sessionId ? ' · Devin joined' : ''}`);
    open.onclick = () => { threadId = t.id; render(); }; row.append(open); return row;
  }));
  if (!threads.length) $('messages').append(el('div', 'empty', `Welcome to #${channel}. Start a conversation with your team.`));
  const t = snapshot.threads.find(t => t.id === threadId);
  $('thread-panel').hidden = !t;
  if (t) {
    $('thread-messages').replaceChildren(...t.messages.map(message));
    $('session-link').replaceChildren();
    if (t.sessionUrl) { const a = el('a', '', 'Open Devin session ↗'); a.href = t.sessionUrl; a.target = '_blank'; a.rel = 'noopener noreferrer'; $('session-link').append(a); }
    $('session-link').append(el('span', 'delivery', t.error || t.pollError || (t.status === 'webhook-delivered' ? 'Automation accepted the webhook; no session ID returned' : t.status)));
    $('reply-author').textContent = snapshot.users.find(u => u.id === $('author').value)?.name || '';
  }
}
async function refresh() {
  try { const r = await fetch('/api/state'); if (!r.ok) throw new Error('Workspace unavailable'); snapshot = await r.json(); render(); }
  catch { $('error').textContent = 'Workspace is disconnected. Messages have not been discarded.'; }
}
async function send(text, id) {
  if (sending) return;
  const payload = { channel, threadId: id, author: $('author').value, text: text.value };
  if (pending && JSON.stringify(pending.payload) !== JSON.stringify(payload)) {
    $('error').textContent = 'An earlier send is unconfirmed. Retry the original message before sending another.';
    return;
  }
  pending ||= { payload, composer: text.id, requestId: crypto.randomUUID() };
  sessionStorage.setItem('pending-message', JSON.stringify(pending));
  sending = true; $('error').textContent = '';
  try {
    const r = await fetch('/api/messages', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workspace-Client': 'mock-slack' }, body: JSON.stringify({ ...pending.payload, requestId: pending.requestId }) });
    const data = await r.json(); if (!r.ok) throw new Error(data.error);
    pending = null; sessionStorage.removeItem('pending-message');
    threadId = data.id; text.value = ''; await refresh();
  } catch (e) { $('error').textContent = `${e.message}. Check the thread before sending again.`; }
  finally { sending = false; }
}
$('compose').onsubmit = e => { e.preventDefault(); send($('message'), null); };
$('reply').onsubmit = e => { e.preventDefault(); send($('reply-text'), threadId); };
$('close-thread').onclick = () => { threadId = null; render(); };
$('author').onchange = render;
await refresh();
if (pending) {
  channel = pending.payload.channel; threadId = pending.payload.threadId;
  $('author').value = pending.payload.author; $(pending.composer).value = pending.payload.text; render();
}
setInterval(refresh, 2000);
