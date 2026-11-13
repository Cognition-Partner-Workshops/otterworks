// Stand-in for the dealer platform API and the OEM notice feed, used by the Playwright suite.
import { createServer } from 'node:http';

const port = Number(process.env.STUB_PORT || 5199);
const EMAIL = 'dealer-ops@dealer.example';
const DEALER_ID = 'D-1001';
const TOKEN =
  'v1.eyJzdWIiOiJkZWFsZXItb3BzQGRlYWxlci5leGFtcGxlIiwiZGVhbGVyIjoiRC0xMDAxIiwicm9sZXMiOlsiZGVhbGVyIl0sImlhdCI6MTc5ODc2MTYwMCwiZXhwIjoxNzk4NzY1MjAwfQ.aQiSk3ln-G_hMxS28Rm8xvC-7P0';

const inventory = [
  { vin: '1VSLA0000AA000001', model: 'Ranger LT', year: 2026, status: 'AVAILABLE', priceCents: 3899000, imageUrl: '/favicon.ico' },
  { vin: '1VSLA0000AA000002', model: 'Harbor XL', year: 2025, status: 'SOLD', priceCents: 4525000, imageUrl: '/favicon.ico' },
  { vin: '1VSLA0000AA000003', model: 'Ranger Sport', year: 2026, status: 'IN_TRANSIT', priceCents: 4100000, imageUrl: '/favicon.ico' },
];
const claims = [
  { id: 'WC-1', vin: '1VSLA0000AA000002', status: 'APPROVED', description: 'Wiper motor replaced', submittedAt: '2026-01-04T09:00:00Z' },
];
const notices = [
  { id: 'N-1', title: 'Brake hose inspection', severity: 'critical', publishedAt: '2026-02-01T12:00:00Z', body: 'Inspect front brake hoses before delivery.' },
  { id: 'N-2', title: 'Holiday parts cut-off', severity: 'info', publishedAt: '2026-01-10T12:00:00Z', body: 'Order by Friday for delivery before the break.' },
];

function send(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(body === undefined ? '' : JSON.stringify(body));
}

function readBody(req) {
  return new Promise(resolve => {
    let data = '';
    req.on('data', chunk => (data += chunk));
    req.on('end', () => resolve(data ? JSON.parse(data) : {}));
  });
}

createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${port}`);
  const route = `${req.method} ${url.pathname}`;

  if (route === 'GET /healthz') return send(res, 200, { status: 'ok' });
  if (route === 'GET /dealer-notices.json') return send(res, 200, notices);
  if (route === 'POST /api/identity/signin') {
    const { email, password } = await readBody(req);
    if (email !== EMAIL || !password || password === 'wrong') return send(res, 401, { error: 'invalid_credentials' });
    return send(res, 200, { accessToken: TOKEN, tokenType: 'Bearer', expiresIn: 3600, dealerId: DEALER_ID });
  }
  if (req.headers.authorization !== `Bearer ${TOKEN}`) return send(res, 401, { error: 'unauthorized' });
  if (route === 'GET /api/dealer/inventory') return send(res, 200, inventory);
  if (route === 'GET /api/warranty/claims') return send(res, 200, claims);
  if (route === 'POST /api/warranty/claims') {
    const { vin, description } = await readBody(req);
    const claim = { id: `WC-${claims.length + 1}`, vin, status: 'SUBMITTED', description, submittedAt: new Date().toISOString() };
    claims.push(claim);
    return send(res, 201, claim);
  }
  return send(res, 404, { error: 'not_found' });
}).listen(port, '127.0.0.1', () => console.log(`stub upstream listening on ${port}`));
