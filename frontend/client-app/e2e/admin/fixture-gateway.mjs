import { createServer } from 'node:http';

const timestamp = '2026-01-15T12:00:00.000Z';
const names = ['Alice Morgan', 'Ben Carter', 'Chloe Patel', 'Daniel Kim', 'Emma Wilson', 'Felix Garcia', 'Grace Chen', 'Henry Brown', 'Isla Davis', 'James Taylor', 'Keira Singh', 'Leo Martin', 'Maya Jones', 'Noah Clark'];
const seed = names.map((display_name, index) => ({
  id: `fixture-user-${String(index + 1).padStart(2, '0')}`,
  display_name,
  email: index === 0 ? 'admin@otterworks.dev' : `${display_name.toLowerCase().replace(' ', '.')}@otterworks.dev`,
  role: ['admin', 'editor', 'viewer'][index % 3],
  status: ['active', 'active', 'suspended', 'pending'][index % 4],
  avatar_url: null,
  created_at: `2025-11-${String(index + 1).padStart(2, '0')}T09:00:00.000Z`,
  last_login_at: index % 4 === 3 ? null : `2026-01-${String(index + 1).padStart(2, '0')}T10:30:00.000Z`,
  storage_quota: { used_bytes: (index + 1) * 64 * 1024 ** 2, quota_bytes: 5 * 1024 ** 3 },
  metadata: { department: ['Engineering', 'Marketing', 'Finance', 'Operations', ''][index % 5], documents_count: index * 3 },
}));
let users;
let auditLogs;
function reset() {
  users = structuredClone(seed);
  auditLogs = seed.map((user, index) => ({
    id: `fixture-event-${index + 1}`, actor_id: user.id, actor_email: user.email,
    action: 'user.login', resource_type: 'User', resource_id: user.id,
    created_at: timestamp, ip_address: '192.0.2.10', changes_made: null,
  }));
}
reset();

function summary() {
  return {
    users: {
      total: users.length,
      active: users.filter(user => user.status === 'active').length,
      suspended: users.filter(user => user.status === 'suspended').length,
      by_role: Object.fromEntries(['admin', 'editor', 'viewer'].map(role => [role, users.filter(user => user.role === role).length])),
    },
    storage: { total_used_bytes: users.reduce((sum, user) => sum + user.storage_quota.used_bytes, 0), by_tier: { standard: users.length } },
    audit: { total_events: auditLogs.length, top_actions: { 'user.login': auditLogs.filter(event => event.action === 'user.login').length, 'user.updated': auditLogs.filter(event => event.action === 'user.updated').length } },
  };
}

createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const path = url.pathname;
  const send = (status, body) => {
    res.writeHead(status, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type, Authorization', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS' });
    res.end(body === undefined ? undefined : JSON.stringify(body));
  };
  try {
    if (req.method === 'OPTIONS') return send(204);
    if (req.method === 'POST' && path === '/__reset') {
      reset();
      return send(200, { status: 'reset' });
    }
    if (req.method === 'POST' && path === '/api/v1/auth/login') {
      let body = '';
      for await (const chunk of req) body += chunk;
      const credentials = JSON.parse(body);
      if (credentials.email !== 'admin@otterworks.dev' || credentials.password !== 'Admin123!') return send(401, { error: 'Invalid credentials' });
      return send(200, { accessToken: 'fixture-admin-token', user: { id: seed[0].id, email: seed[0].email, displayName: seed[0].display_name } });
    }
    if (req.method === 'GET' && path === '/api/v1/admin/metrics/summary') return send(200, summary());
    if (req.method === 'GET' && path === '/api/v1/admin/users') return send(200, { users });
    if (req.method === 'GET' && path === '/api/v1/admin/audit-logs') {
      const actor = url.searchParams.get('actor_id');
      return send(200, { audit_logs: auditLogs.filter(event => !actor || event.actor_id === actor) });
    }
    const match = path.match(/^\/api\/v1\/admin\/users\/([^/]+)(?:\/(suspend|activate))?$/);
    if (match) {
      const user = users.find(user => user.id === decodeURIComponent(match[1]));
      if (!user) return send(404, { error: 'User not found' });
      if (req.method === 'GET' && !match[2]) return send(200, user);
      if ((req.method === 'PUT' && match[2]) || (req.method === 'DELETE' && !match[2])) {
        if (req.method === 'DELETE') users = users.filter(entry => entry.id !== user.id);
        else user.status = match[2] === 'suspend' ? 'suspended' : 'active';
        auditLogs.push({ id: `fixture-event-${auditLogs.length + 1}`, actor_id: seed[0].id, actor_email: seed[0].email, action: req.method === 'DELETE' ? 'user.deleted' : 'user.updated', resource_type: 'User', resource_id: user.id, created_at: timestamp, ip_address: '192.0.2.10', changes_made: req.method === 'DELETE' ? null : { status: user.status } });
        return send(req.method === 'DELETE' ? 204 : 200, req.method === 'DELETE' ? undefined : user);
      }
    }
    return send(404, { error: 'Not found' });
  } catch (error) {
    return send(error instanceof SyntaxError ? 400 : 500, { error: error instanceof SyntaxError ? 'Invalid JSON' : 'Internal server error' });
  }
}).listen(Number(process.env.FIXTURE_GATEWAY_PORT || 8099), '127.0.0.1', () => {
  console.log(`Admin fixture gateway listening on http://127.0.0.1:${process.env.FIXTURE_GATEWAY_PORT || 8099}`);
});
