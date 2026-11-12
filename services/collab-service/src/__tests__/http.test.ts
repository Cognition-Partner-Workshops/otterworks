import express from 'express';
import { createServer, type IncomingMessage, type Server } from 'http';
import jwt from 'jsonwebtoken';
import { AwarenessService } from '../services/awareness';
import { PresenceHandler } from '../handlers/presence';
import {
  authorizeYWebsocketUpgrade,
  createCollabRouter,
  documentIdFromRoom,
} from '../handlers/http';
import type {
  AccessRequest,
  DocumentAccessChecker,
  DocumentPermission,
} from '../services/document-access';

const JWT_SECRET = 'test-secret-key-for-http-tests';
const mockLogger = {
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  debug: jest.fn(),
} as never;

const DOC_A = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const DOC_B = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';

class MapAccess implements DocumentAccessChecker {
  grants = new Map<string, DocumentPermission>();
  fail = false;
  async checkAccess({
    documentId,
    user,
  }: AccessRequest): Promise<DocumentPermission | null> {
    if (this.fail) throw new Error('down');
    return this.grants.get(`${documentId}:${user.userId}`) ?? null;
  }
}

function token(sub: string): string {
  return jwt.sign({ sub, name: sub, email: `${sub}@test.com` }, JWT_SECRET, {
    expiresIn: '1h',
  }); // nosemgrep: javascript.jsonwebtoken.security.jwt-hardcode.hardcoded-jwt-secret
}

describe('collab HTTP routes', () => {
  let server: Server;
  let base: string;
  let awareness: AwarenessService;
  let access: MapAccess;

  beforeAll((done) => {
    awareness = new AwarenessService(mockLogger);
    access = new MapAccess();
    const presenceHandler = new PresenceHandler(awareness, mockLogger);
    const app = express();
    app.use(
      '/api/v1/collab',
      createCollabRouter({
        jwtSecret: JWT_SECRET,
        documentAccess: access,
        awareness,
        presenceHandler,
        logger: mockLogger,
      }),
    );
    server = createServer(app).listen(0, () => {
      const addr = server.address();
      base = `http://localhost:${typeof addr === 'object' && addr ? addr.port : 0}`;
      done();
    });
  });

  afterAll((done) => {
    server.close(done);
  });

  beforeEach(() => {
    access.grants.clear();
    access.fail = false;
    awareness.addUser(DOC_A, 'sock-alice', 'alice', 'Alice', 'alice@test.com');
    awareness.addUser(DOC_B, 'sock-bob', 'bob', 'Bob', 'bob@test.com');
  });

  afterEach(() => {
    awareness.removeUser('sock-alice');
    awareness.removeUser('sock-bob');
  });

  const get = (path: string, who?: string) =>
    fetch(`${base}${path}`, {
      headers: who ? { Authorization: `Bearer ${token(who)}` } : {},
    });

  it('requires a valid bearer token', async () => {
    expect((await get('/api/v1/collab/documents')).status).toBe(401);
    const bad = await fetch(`${base}/api/v1/collab/documents`, {
      headers: { Authorization: 'Bearer nope' },
    });
    expect(bad.status).toBe(401);
  });

  it('lists only the documents the caller is present in', async () => {
    const res = await get('/api/v1/collab/documents', 'alice');
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual({ documents: [{ documentId: DOC_A, userCount: 1 }], count: 1 });

    const mallory = await (await get('/api/v1/collab/documents', 'mallory')).json();
    expect(mallory).toEqual({ documents: [], count: 0 });
  });

  it('returns presence only when document-service grants the caller access', async () => {
    access.grants.set(`${DOC_A}:alice`, 'edit');
    const owner = await get(`/api/v1/collab/documents/${DOC_A}/presence`, 'alice');
    expect(owner.status).toBe(200);
    expect(((await owner.json()) as { count: number }).count).toBe(1);

    const mallory = await get(`/api/v1/collab/documents/${DOC_A}/presence`, 'mallory');
    expect(mallory.status).toBe(404);
    expect(await mallory.text()).not.toContain('alice@test.com');
  });

  it('fails closed when the access check is unavailable', async () => {
    access.fail = true;
    const res = await get(`/api/v1/collab/documents/${DOC_A}/presence`, 'alice');
    expect(res.status).toBe(503);
  });
});

describe('authorizeYWebsocketUpgrade', () => {
  const access = new MapAccess();
  const deps = { jwtSecret: JWT_SECRET, documentAccess: access, logger: mockLogger };
  const request = (url: string, authorization?: string) =>
    ({
      url,
      headers: { host: 'collab:8084', ...(authorization ? { authorization } : {}) },
    }) as IncomingMessage;

  beforeEach(() => {
    access.grants.clear();
    access.fail = false;
  });

  it('maps room names to document ids', () => {
    expect(documentIdFromRoom(`/document-${DOC_A}`)).toBe(DOC_A);
    expect(documentIdFromRoom(`/${DOC_A}`)).toBe(DOC_A);
    expect(documentIdFromRoom(`//document-${DOC_A}/extra`)).toBe(DOC_A);
  });

  it('rejects missing and invalid tokens with 401', async () => {
    expect(
      await authorizeYWebsocketUpgrade(request(`/document-${DOC_A}`), deps),
    ).toMatchObject({ allowed: false, status: 401 });
    expect(
      await authorizeYWebsocketUpgrade(request(`/document-${DOC_A}?token=garbage`), deps),
    ).toMatchObject({ allowed: false, status: 401 });
  });

  it('allows only edit-permitted callers onto the room', async () => {
    access.grants.set(`${DOC_A}:alice`, 'edit');
    access.grants.set(`${DOC_A}:viewer`, 'view');
    expect(
      await authorizeYWebsocketUpgrade(
        request(`/document-${DOC_A}?token=${token('alice')}`),
        deps,
      ),
    ).toMatchObject({ allowed: true, documentId: DOC_A });
    expect(
      await authorizeYWebsocketUpgrade(
        request(`/document-${DOC_A}`, `Bearer ${token('alice')}`),
        deps,
      ),
    ).toMatchObject({ allowed: true });
    expect(
      await authorizeYWebsocketUpgrade(
        request(`/document-${DOC_A}?token=${token('viewer')}`),
        deps,
      ),
    ).toMatchObject({ allowed: false, status: 403 });
    expect(
      await authorizeYWebsocketUpgrade(
        request(`/document-${DOC_A}?token=${token('mallory')}`),
        deps,
      ),
    ).toMatchObject({ allowed: false, status: 403 });
  });

  it('fails closed when document-service is unavailable', async () => {
    access.fail = true;
    expect(
      await authorizeYWebsocketUpgrade(
        request(`/document-${DOC_A}?token=${token('alice')}`),
        deps,
      ),
    ).toMatchObject({ allowed: false, status: 503 });
  });
});
