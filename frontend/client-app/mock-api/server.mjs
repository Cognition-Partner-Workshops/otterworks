import http from 'node:http';

const port = Number(process.env.MOCK_PORT || 4010);
const now = '2026-11-01T12:00:00Z';
let state;
let contents;
function reset() {
  contents = new Map([['file-1', Buffer.from('Harbor report mock content')]]);
  state = {
    profile: { id: 'tester', email: 'tester@example.com', displayName: 'Harbor Tester' },
    files: [{ id: 'file-1', name: 'Harbor report.txt', mimeType: 'text/plain', sizeBytes: 25, ownerId: 'tester', folderId: null, createdAt: now, updatedAt: now }],
    folders: [{ id: 'folder-1', name: 'Voyages', createdAt: now, updatedAt: now }],
    documents: [{ id: 'doc-1', title: 'Voyage notes', content: '<p>Welcome aboard the harbor.</p>', ownerId: 'tester', ownerName: 'Harbor Tester', sharedWith: [], collaborators: [], tags: [], wordCount: 5, createdAt: now, updatedAt: now }],
    notifications: [{ id: 'notice-1', type: 'system', title: 'Harbor update', message: 'Your voyage report is ready', read: false, createdAt: now }],
    settings: { notificationEmail: true, notificationInApp: true, notificationDesktop: false, theme: 'light', language: 'en' },
  };
}
reset();
const paginate = (data) => ({ data, items: data, total: data.length, page: 1, pageSize: 50, hasMore: false });
const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, PUT, DELETE, OPTIONS');
  const send = (data, status = 200) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(data)); };
  if (req.method === 'OPTIONS') return send({});
  const url = new URL(req.url, `http://127.0.0.1:${port}`);
  const path = url.pathname.replace(/^\/api\/v1/, '');
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks);
  let body = {};
  if (req.headers['content-type']?.includes('application/json') && raw.length) {
    try { body = JSON.parse(raw); } catch { return send({ message: 'Invalid JSON' }, 400); }
  }
  if (path === '/__reset' && req.method === 'POST') { reset(); return send({ ok: true }); }
  if (path === '/health') return send({ ok: true });
  if (path === '/auth/login') {
    if (body.email !== 'tester@example.com' || body.password !== 'HarborPass123!') return send({ message: 'Invalid credentials' }, 401);
    const payload = Buffer.from(JSON.stringify({ sub: 'tester', exp: 4102444800 })).toString('base64url');
    return send({ accessToken: `mock.${payload}.mock`, refreshToken: 'mock-refresh', expiresAt: 4102444800 });
  }
  if (!req.headers.authorization && !path.startsWith('/download/')) return send({ message: 'Unauthorized' }, 401);
  if (path === '/auth/profile') { Object.assign(state.profile, body); return send(state.profile); }
  if (path === '/auth/logout') return send({});
  if (path === '/settings') { Object.assign(state.settings, body); return send(state.settings); }
  if (path === '/files/activity') return send({ items: [{ id: 'activity-1', type: 'upload', description: 'Harbor report uploaded', actorName: 'Harbor Tester', resourceName: 'Harbor report.txt', resourceType: 'file', resourceId: 'file-1', createdAt: now }] });
  if (path === '/files/upload' && req.method === 'POST') {
    const name = /filename="([^"]+)"/.exec(raw.toString())?.[1];
    if (!name) return send({ message: 'Missing file' }, 400);
    const boundary = /boundary=(?:"([^"]+)"|([^;]+))/.exec(req.headers['content-type'] || '');
    if (!boundary) return send({ message: 'Missing multipart boundary' }, 400);
    const start = raw.indexOf('\r\n\r\n', raw.indexOf(`filename="${name}"`)) + 4;
    const end = raw.indexOf(`\r\n--${boundary[1] || boundary[2]}`, start);
    if (start < 4 || end < start) return send({ message: 'Invalid multipart body' }, 400);
    const content = raw.subarray(start, end);
    const file = { ...state.files[0], id: `file-${state.files.length + 1}`, name, sizeBytes: content.length };
    contents.set(file.id, content);
    state.files.push(file); return send({ file }, 201);
  }
  if (path === '/files' || path === '/files/shared' || path === '/files/trash') {
    const files = path === '/files/trash' ? [] : state.files;
    return send({ files, total: files.length, page: 1, pageSize: 50 });
  }
  if (path === '/folders') {
    if (req.method === 'POST') { const folder = { id: `folder-${state.folders.length + 1}`, ...body, createdAt: now, updatedAt: now }; state.folders.push(folder); return send(folder, 201); }
    return send({ folders: url.searchParams.has('parent_id') ? [] : state.folders });
  }
  if (/^\/files\/[^/]+\/download$/.test(path)) {
    const id = path.split('/')[2];
    if (!contents.has(id)) return send({ message: 'File not found' }, 404);
    return send({ url: `http://127.0.0.1:${port}/download/${id}`, expiresInSecs: 3600 });
  }
  if (path.startsWith('/download/')) {
    const file = state.files.find(f => f.id === path.split('/')[2]);
    if (!file) return send({ message: 'File not found' }, 404);
    res.writeHead(200, { 'Content-Type': file.mimeType, 'Content-Disposition': `attachment; filename="${file.name.replace(/["\r\n]/g, '_')}"` });
    return res.end(contents.get(file.id));
  }
  if (path.startsWith('/files/')) { const file = state.files.find(f => f.id === path.split('/')[2]); return send(file || { message: 'File not found' }, file ? 200 : 404); }
  if (path === '/documents') return send(paginate(state.documents));
  if (path.startsWith('/documents/')) { const doc = state.documents.find(d => d.id === path.split('/')[2]); if (!doc) return send({ message: 'Document not found' }, 404); Object.assign(doc, body); return send(doc); }
  if (path === '/notifications/unread-count') return send({ count: state.notifications.filter(n => !n.read).length });
  if (path === '/notifications/read-all' || /\/notifications\/[^/]+\/read/.test(path)) { state.notifications.forEach(n => { n.read = true; }); return send({}); }
  if (path === '/notifications') return send(paginate(state.notifications));
  if (path === '/search/suggest') return send({ suggestions: ['Harbor'] });
  if (path === '/search') { const results = state.files.filter(f => f.name.toLowerCase().includes((url.searchParams.get('q') || '').toLowerCase())).map(f => ({ id: f.id, title: f.name, type: 'file', updatedAt: now, contentSnippet: 'Harbor report mock content' })); return send({ results, total: results.length }); }
  if (path === '/analytics/margins') return send({ asOfDate: '2026-11-01', source: 'mock', lastSyncAt: now, kpis: { grossMarginPct: 42, avgCogsUsd: 12, salmonIndex: 100, freightIndex: 90 }, rows: [{ sku: 'HARBOR-01', name: 'Harbor salmon', category: 'Seafood', supplier: 'Harbor supply', listPriceUsd: 20, commodityCostUsd: 8, freightCostUsd: 2, overheadCostUsd: 2, cogsUsd: 12, marginPct: 40 }] });
  if (path === '/analytics/margins/series') return send({ points: [{ marginDate: '2026-11-01', marginPct: 40 }] });
  if (path === '/analytics/market/prices') return send({ prices: [] });
  if (path === '/analytics/margins/export') { res.writeHead(200, { 'Content-Type': 'text/csv' }); return res.end('sku,name,margin_pct\nHARBOR-01,Harbor salmon,40\n'); }
  return send({ message: `Unimplemented mock route: ${req.method} ${path}` }, 404);
});
server.on('upgrade', (_req, socket) => socket.end('HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n\r\n'));
server.listen(port, '127.0.0.1', () => console.log(`Mock API listening on http://127.0.0.1:${port}`));
