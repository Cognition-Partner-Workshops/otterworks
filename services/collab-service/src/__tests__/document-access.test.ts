import express from 'express';
import { createServer, type IncomingMessage, type Server } from 'http';
import type { AddressInfo } from 'net';
import jwt from 'jsonwebtoken';
import {
  DocumentAccessService,
  type DocumentAccessChecker,
} from '../services/document-access';
import { authorizeYjsUpgrade, documentIdFromYjsUrl } from '../handlers/yjs-upgrade';
import { createCollabApiRouter } from '../routes/collab-api';
import { AwarenessService } from '../services/awareness';
import { PresenceHandler } from '../handlers/presence';

const JWT_SECRET = 'test-secret-key-for-unit-tests';
const OWNER = '11111111-1111-4111-8111-111111111111';
const INTRUDER = '22222222-2222-4222-8222-222222222222';
const OWNER_DOC = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const INTRUDER_DOC = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';

const mockLogger = {
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  debug: jest.fn(),
} as never;

function tokenFor(userId: string): string {
  return jwt.sign({ sub: userId }, JWT_SECRET, { expiresIn: '1h' }); // nosemgrep: javascript.jsonwebtoken.security.jwt-hardcode.hardcoded-jwt-secret
}

const ownersByDocument: Record<string, string> = {
  [OWNER_DOC]: OWNER,
  [INTRUDER_DOC]: INTRUDER,
};
const ownerOnlyAccess: DocumentAccessChecker = {
  getAccess: async (documentId, userId) => {
    const allowed = ownersByDocument[documentId] === userId;
    return { canRead: allowed, canEdit: allowed };
  },
};

describe('DocumentAccessService', () => {
  function serviceWith(fetchImpl: jest.Mock, cacheTtlMs = 0) {
    return new DocumentAccessService(
      {
        documentServiceUrl: 'http://document-service:8083/',
        timeoutMs: 1000,
        cacheTtlMs,
        fetchImpl: fetchImpl as unknown as typeof fetch,
      },
      mockLogger,
    );
  }

  it('asks document-service as the caller and grants access on 200', async () => {
    const fetchImpl = jest.fn().mockResolvedValue({ status: 200 });
    const access = await serviceWith(fetchImpl).getAccess(OWNER_DOC, OWNER, 'tok');

    expect(access).toEqual({ canRead: true, canEdit: true });
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe(`http://document-service:8083/api/v1/documents/${OWNER_DOC}`);
    expect(init.headers.Authorization).toBe('Bearer tok');
  });

  it.each([401, 403, 404, 422, 500, 503])(
    'denies access on status %i',
    async (status) => {
      const fetchImpl = jest.fn().mockResolvedValue({ status });
      const access = await serviceWith(fetchImpl).getAccess(OWNER_DOC, INTRUDER, 'tok');
      expect(access).toEqual({ canRead: false, canEdit: false });
    },
  );

  it('denies access when document-service cannot be reached', async () => {
    const fetchImpl = jest.fn().mockRejectedValue(new Error('ECONNREFUSED'));
    const access = await serviceWith(fetchImpl).getAccess(OWNER_DOC, OWNER, 'tok');
    expect(access).toEqual({ canRead: false, canEdit: false });
  });

  it.each(['', 'doc-1', '../admin', `${OWNER_DOC}/../x`])(
    'denies malformed document id %p without calling document-service',
    async (documentId) => {
      const fetchImpl = jest.fn();
      const access = await serviceWith(fetchImpl).getAccess(documentId, OWNER, 'tok');
      expect(access.canRead).toBe(false);
      expect(fetchImpl).not.toHaveBeenCalled();
    },
  );

  it('caches a decision per user, never across users', async () => {
    const fetchImpl = jest
      .fn()
      .mockResolvedValueOnce({ status: 200 })
      .mockResolvedValueOnce({ status: 403 });
    const service = serviceWith(fetchImpl, 60000);

    expect((await service.getAccess(OWNER_DOC, OWNER, 'tok')).canRead).toBe(true);
    expect((await service.getAccess(OWNER_DOC, OWNER, 'tok')).canRead).toBe(true);
    expect((await service.getAccess(OWNER_DOC, INTRUDER, 'tok2')).canRead).toBe(false);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it('does not cache a failed lookup', async () => {
    const fetchImpl = jest
      .fn()
      .mockRejectedValueOnce(new Error('timeout'))
      .mockResolvedValueOnce({ status: 200 });
    const service = serviceWith(fetchImpl, 60000);

    expect((await service.getAccess(OWNER_DOC, OWNER, 'tok')).canRead).toBe(false);
    expect((await service.getAccess(OWNER_DOC, OWNER, 'tok')).canRead).toBe(true);
  });
});

describe('y-websocket upgrade authorization', () => {
  function upgradeRequest(path: string, authorization?: string): IncomingMessage {
    return {
      url: path,
      headers: { host: 'localhost:8084', ...(authorization ? { authorization } : {}) },
    } as IncomingMessage;
  }

  it('reads the document id from the room in the URL', () => {
    expect(documentIdFromYjsUrl(new URL(`http://x/document-${OWNER_DOC}?token=t`))).toBe(
      OWNER_DOC,
    );
    expect(documentIdFromYjsUrl(new URL('http://x/other-room'))).toBeNull();
    expect(documentIdFromYjsUrl(new URL('http://x/'))).toBeNull();
  });

  it('rejects a missing or invalid token with 401', async () => {
    const noToken = await authorizeYjsUpgrade(
      upgradeRequest(`/document-${OWNER_DOC}`),
      JWT_SECRET,
      ownerOnlyAccess,
    );
    const badToken = await authorizeYjsUpgrade(
      upgradeRequest(`/document-${OWNER_DOC}?token=not-a-jwt`),
      JWT_SECRET,
      ownerOnlyAccess,
    );
    expect(noToken).toMatchObject({ allowed: false, status: 401 });
    expect(badToken).toMatchObject({ allowed: false, status: 401 });
  });

  it("rejects a valid token for someone else's document with 403", async () => {
    const decision = await authorizeYjsUpgrade(
      upgradeRequest(`/document-${OWNER_DOC}?token=${tokenFor(INTRUDER)}`),
      JWT_SECRET,
      ownerOnlyAccess,
    );
    expect(decision).toMatchObject({ allowed: false, status: 403 });
  });

  it('rejects a room that does not name a document with 403', async () => {
    const decision = await authorizeYjsUpgrade(
      upgradeRequest(`/anything?token=${tokenFor(OWNER)}`),
      JWT_SECRET,
      ownerOnlyAccess,
    );
    expect(decision).toMatchObject({ allowed: false, status: 403 });
  });

  it('allows the owner, by query token or Authorization header', async () => {
    const byQuery = await authorizeYjsUpgrade(
      upgradeRequest(`/document-${OWNER_DOC}?token=${tokenFor(OWNER)}`),
      JWT_SECRET,
      ownerOnlyAccess,
    );
    const byHeader = await authorizeYjsUpgrade(
      upgradeRequest(`/document-${OWNER_DOC}`, `Bearer ${tokenFor(OWNER)}`),
      JWT_SECRET,
      ownerOnlyAccess,
    );
    expect(byQuery).toMatchObject({
      allowed: true,
      userId: OWNER,
      documentId: OWNER_DOC,
    });
    expect(byHeader).toMatchObject({
      allowed: true,
      userId: OWNER,
      documentId: OWNER_DOC,
    });
  });
});

describe('collab REST API', () => {
  let server: Server;
  let baseUrl: string;

  beforeAll((done) => {
    const awareness = new AwarenessService(mockLogger);
    const presenceHandler = new PresenceHandler(awareness, mockLogger);
    awareness.addUser(OWNER_DOC, 'socket-1', OWNER, 'Owner', 'owner@test.com');
    awareness.addUser(
      INTRUDER_DOC,
      'socket-2',
      INTRUDER,
      'Intruder',
      'intruder@test.com',
    );

    const app = express();
    app.use(
      '/api/v1/collab',
      createCollabApiRouter({
        jwtSecret: JWT_SECRET,
        presenceHandler,
        documentAccess: ownerOnlyAccess,
        logger: mockLogger,
      }),
    );
    server = createServer(app).listen(0, () => {
      baseUrl = `http://localhost:${(server.address() as AddressInfo).port}/api/v1/collab`;
      done();
    });
  });

  afterAll((done) => {
    server.close(done);
  });

  function get(path: string, userId?: string) {
    return fetch(`${baseUrl}${path}`, {
      headers: userId ? { Authorization: `Bearer ${tokenFor(userId)}` } : {},
    });
  }

  it('requires a valid token', async () => {
    expect((await get('/documents')).status).toBe(401);
    expect((await get(`/documents/${OWNER_DOC}/presence`)).status).toBe(401);
  });

  it('lists only active documents the caller can open', async () => {
    const res = await get('/documents', INTRUDER);
    const body = (await res.json()) as {
      count: number;
      documents: { documentId: string }[];
    };

    expect(res.status).toBe(200);
    expect(body.count).toBe(1);
    expect(body.documents.map((d) => d.documentId)).toEqual([INTRUDER_DOC]);
  });

  it('hides presence of a document the caller cannot open', async () => {
    const res = await get(`/documents/${OWNER_DOC}/presence`, INTRUDER);
    const body = await res.text();

    expect(res.status).toBe(404);
    expect(body).not.toContain('owner@test.com');
  });

  it('returns presence to a caller who can open the document', async () => {
    const res = await get(`/documents/${OWNER_DOC}/presence`, OWNER);
    const body = (await res.json()) as { users: { userId: string }[] };

    expect(res.status).toBe(200);
    expect(body.users[0].userId).toBe(OWNER);
  });

  it('limits how often one caller can query', async () => {
    const app = express();
    app.use(
      createCollabApiRouter({
        jwtSecret: JWT_SECRET,
        presenceHandler: new PresenceHandler(
          new AwarenessService(mockLogger),
          mockLogger,
        ),
        documentAccess: ownerOnlyAccess,
        logger: mockLogger,
        rateLimitPerMinute: 2,
      }),
    );
    const limited = createServer(app);
    await new Promise<void>((resolve) => limited.listen(0, resolve));
    const url = `http://localhost:${(limited.address() as AddressInfo).port}/documents`;
    const call = (userId: string) =>
      fetch(url, { headers: { Authorization: `Bearer ${tokenFor(userId)}` } });
    try {
      expect((await call(OWNER)).status).toBe(200);
      expect((await call(OWNER)).status).toBe(200);
      expect((await call(OWNER)).status).toBe(429);
      expect((await call(INTRUDER)).status).toBe(200);
    } finally {
      await new Promise((resolve) => limited.close(resolve));
    }
  });
});
