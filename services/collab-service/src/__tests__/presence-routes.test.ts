import express from 'express';
import { createServer, Server } from 'http';
import type { AddressInfo } from 'net';
import jwt from 'jsonwebtoken';
import { AwarenessService } from '../services/awareness';
import { PresenceHandler } from '../handlers/presence';
import { createPresenceRouter } from '../routes/presence';

const JWT_SECRET = 'test-secret-key-for-unit-tests';

function createToken(payload: Record<string, unknown>): string {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: '1h' }); // nosemgrep: javascript.jsonwebtoken.security.jwt-hardcode.hardcoded-jwt-secret
}

const mockLogger = {
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  debug: jest.fn(),
  fatal: jest.fn(),
  trace: jest.fn(),
  child: jest.fn().mockReturnThis(),
  level: 'info',
} as never;

describe('presence HTTP routes', () => {
  let server: Server;
  let baseUrl: string;
  let awareness: AwarenessService;

  const userAToken = createToken({ sub: 'user-a', email: 'a@test.com', name: 'A' });
  const userBToken = createToken({ sub: 'user-b', email: 'b@test.com', name: 'B' });
  const outsiderToken = createToken({
    sub: 'attacker',
    email: 'attacker@test.com',
    name: 'Attacker',
    roles: ['USER'],
  });

  interface JsonBody {
    documentId?: string;
    documents?: Array<{ documentId: string; userCount: number }>;
    users?: Array<{ userId: string }>;
    count?: number;
  }

  const readJson = (res: Response): Promise<JsonBody> => res.json() as Promise<JsonBody>;

  const get = (path: string, token?: string) =>
    fetch(`${baseUrl}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

  beforeAll((done) => {
    awareness = new AwarenessService(mockLogger);
    const presenceHandler = new PresenceHandler(awareness, mockLogger);

    const app = express();
    app.use(createPresenceRouter(presenceHandler, JWT_SECRET, mockLogger));

    server = createServer(app);
    server.listen(0, () => {
      baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
      done();
    });
  });

  afterAll((done) => {
    server.close(() => done());
  });

  beforeEach(() => {
    for (const socketId of ['socket-a', 'socket-b']) {
      awareness.removeUser(socketId);
    }
    awareness.addUser('tenantA-secret-doc', 'socket-a', 'user-a', 'A', 'a@test.com');
    awareness.addUser('tenantB-secret-doc', 'socket-b', 'user-b', 'B', 'b@test.com');
  });

  describe('authentication', () => {
    it('rejects unauthenticated requests to the documents listing', async () => {
      const res = await get('/api/v1/collab/documents');
      expect(res.status).toBe(401);
    });

    it('rejects unauthenticated requests to presence', async () => {
      const res = await get('/api/v1/collab/documents/tenantA-secret-doc/presence');
      expect(res.status).toBe(401);
    });

    it('rejects invalid tokens', async () => {
      const res = await get('/api/v1/collab/documents', 'not-a-valid-token');
      expect(res.status).toBe(401);
    });
  });

  describe('GET /api/v1/collab/documents', () => {
    it('does not expose a global listing to a user who is in no document', async () => {
      const res = await get('/api/v1/collab/documents', outsiderToken);
      expect(res.status).toBe(200);
      const body = await readJson(res);
      expect(body).toEqual({ documents: [], count: 0 });
    });

    it('lists only the documents the caller participates in', async () => {
      const res = await get('/api/v1/collab/documents', userAToken);
      expect(res.status).toBe(200);
      const body = await readJson(res);
      expect(body.count).toBe(1);
      expect(body.documents).toEqual([
        { documentId: 'tenantA-secret-doc', userCount: 1 },
      ]);
    });
  });

  describe('GET /api/v1/collab/documents/:id/presence', () => {
    it('returns presence for a document the caller participates in', async () => {
      const res = await get(
        '/api/v1/collab/documents/tenantA-secret-doc/presence',
        userAToken,
      );
      expect(res.status).toBe(200);
      const body = await readJson(res);
      expect(body.documentId).toBe('tenantA-secret-doc');
      expect(body.count).toBe(1);
      expect(body.users?.[0].userId).toBe('user-a');
    });

    it("forbids reading presence of another user's document", async () => {
      const res = await get(
        '/api/v1/collab/documents/tenantA-secret-doc/presence',
        outsiderToken,
      );
      expect(res.status).toBe(403);
      const body = await readJson(res);
      expect(body.users).toBeUndefined();
    });

    it('forbids a participant of one document from reading another', async () => {
      const res = await get(
        '/api/v1/collab/documents/tenantA-secret-doc/presence',
        userBToken,
      );
      expect(res.status).toBe(403);
    });

    it('forbids presence lookups for unknown documents (no existence oracle)', async () => {
      const res = await get(
        '/api/v1/collab/documents/not-a-real-document/presence',
        userAToken,
      );
      expect(res.status).toBe(403);
    });
  });
});
