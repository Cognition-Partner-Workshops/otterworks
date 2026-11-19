import { spawn } from 'node:child_process';
import { once } from 'node:events';
import assert from 'node:assert/strict';
import { test } from 'node:test';

test('mock contract: auth, uploads/downloads, persistence, empty results and reset', async () => {
  const server = spawn(process.execPath, [new URL('./server.mjs', import.meta.url).pathname], { env: { ...process.env, MOCK_PORT: '4011' }, stdio: ['ignore', 'pipe', 'inherit'] });
  try {
    await once(server.stdout, 'data');
    const request = (path, options = {}) => fetch(`http://127.0.0.1:4011${path}`, options);
    const json = (body) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    assert.equal((await request('/api/v1/files')).status, 401);
    assert.equal((await request('/api/v1/auth/login', json({ email: 'tester@example.com', password: 'wrong' }))).status, 401);
    const login = await (await request('/api/v1/auth/login', json({ email: 'tester@example.com', password: 'HarborPass123!' }))).json();
    const headers = { Authorization: `Bearer ${login.accessToken}` };
    const form = new FormData();
    form.append('file', new Blob(['uploaded content']), 'deck.txt');
    const upload = await request('/api/v1/files/upload', { method: 'POST', headers, body: form });
    assert.equal(upload.status, 201);
    const { file } = await upload.json();
    assert.equal(file.sizeBytes, 16);
    const { url } = await (await request(`/api/v1/files/${file.id}/download`, { headers })).json();
    assert.equal(await (await fetch(url)).text(), 'uploaded content');
    assert.equal((await request('/api/v1/files/upload', { method: 'POST', headers })).status, 400);
    assert.equal((await request('/api/v1/files/missing', { headers })).status, 404);
    assert.equal((await request('/api/v1/unknown', { headers })).status, 404);
    assert.equal((await (await request('/api/v1/search?q=missing', { headers })).json()).total, 0);
    await request('/api/v1/documents/doc-1', { method: 'PATCH', headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify({ content: '<p>Saved</p>' }) });
    assert.equal((await (await request('/api/v1/documents/doc-1', { headers })).json()).content, '<p>Saved</p>');
    await request('/__reset', { method: 'POST' });
    assert.equal((await (await request('/api/v1/files', { headers })).json()).total, 1);
  } finally {
    server.kill();
    await once(server, 'exit');
  }
});
