import { randomBytes } from 'crypto';
import { createServer, type Server } from 'http';
import type { AddressInfo } from 'net';
import express from 'express';
import jwt from 'jsonwebtoken';
import { Server as SocketIOServer } from 'socket.io';
import { io as clientIO, Socket as ClientSocket } from 'socket.io-client';
import { CollaborationManager } from '../handlers/collaboration';
import { PresenceHandler } from '../handlers/presence';
import { MetricsCollector } from '../metrics';
import { createAuthMiddleware } from '../middleware/auth';
import { createPresenceRouter } from '../routes/presence';
import { AwarenessService } from '../services/awareness';
import { DocumentAccessChecker } from '../services/document-access';
import { DocumentStore } from '../services/document-store';
import { RedisAdapter } from '../services/redis-adapter';
import { authorizeYjsUpgrade } from '../services/yjs-auth';

const jwtSecret = randomBytes(32).toString('hex');

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

function tokenFor(userId: string, name = userId): string {
  return jwt.sign(
    { sub: userId, name, email: `${userId}@test.io`, type: 'access' },
    jwtSecret,
    {
      expiresIn: '1h',
    },
  );
}

// Grants are `${userId}:${documentId}`; mirrors document-service answering 200 vs 403.
function fakeAccess(grants: string[]): DocumentAccessChecker {
  const allowed = new Set(grants);
  const fetchFn = jest.fn(async (url: string, init?: RequestInit) => {
    const auth = (init?.headers as Record<string, string>).Authorization.replace(
      'Bearer ',
      '',
    );
    const userId = (jwt.decode(auth) as { sub: string }).sub;
    const documentId = decodeURIComponent(url.split('/api/v1/documents/')[1]);
    return new Response(null, {
      status: allowed.has(`${userId}:${documentId}`) ? 200 : 403,
    });
  });
  return new DocumentAccessChecker(
    {
      documentServiceUrl: 'http://document-service:8083',
      timeoutMs: 1000,
      cacheTtlMs: 0,
    },
    mockLogger,
    fetchFn as unknown as typeof fetch,
  );
}

describe('DocumentAccessChecker', () => {
  const options = {
    documentServiceUrl: 'http://docs:8083/',
    timeoutMs: 50,
    cacheTtlMs: 60000,
  };

  it('forwards the caller JWT to GET /api/v1/documents/{id} and allows on 2xx', async () => {
    const fetchFn = jest.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    const checker = new DocumentAccessChecker(options, mockLogger, fetchFn);
    await expect(checker.canAccess('u1', 'tok-1', 'doc-1')).resolves.toBe(true);
    expect(fetchFn).toHaveBeenCalledWith(
      'http://docs:8083/api/v1/documents/doc-1',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer tok-1' }),
      }),
    );
  });

  it.each([401, 403, 404, 500, 302])(
    'denies when document-service answers %i',
    async (status) => {
      const fetchFn = jest.fn().mockResolvedValue(new Response(null, { status }));
      const checker = new DocumentAccessChecker(options, mockLogger, fetchFn);
      await expect(checker.canAccess('u1', 'tok-1', 'doc-1')).resolves.toBe(false);
    },
  );

  it('denies when document-service is unreachable or times out', async () => {
    const down = new DocumentAccessChecker(
      options,
      mockLogger,
      jest.fn().mockRejectedValue(new Error('ECONNREFUSED')),
    );
    await expect(down.canAccess('u1', 'tok-1', 'doc-1')).resolves.toBe(false);

    const slow = new DocumentAccessChecker(
      options,
      mockLogger,
      ((_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(new Error('aborted')));
        })) as unknown as typeof fetch,
    );
    await expect(slow.canAccess('u1', 'tok-1', 'doc-1')).resolves.toBe(false);
  });

  it('caches decisions per user and document', async () => {
    const fetchFn = jest.fn().mockResolvedValue(new Response(null, { status: 200 }));
    const checker = new DocumentAccessChecker(options, mockLogger, fetchFn);
    await checker.canAccess('u1', 'tok-1', 'doc-1');
    await checker.canAccess('u1', 'tok-1', 'doc-1');
    await checker.canAccess('u2', 'tok-2', 'doc-1');
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it('URL-encodes the document id', async () => {
    const fetchFn = jest.fn().mockResolvedValue(new Response(null, { status: 403 }));
    const checker = new DocumentAccessChecker(options, mockLogger, fetchFn);
    await checker.canAccess('u1', 'tok-1', '../admin?x=1');
    expect(fetchFn.mock.calls[0][0]).toBe(
      'http://docs:8083/api/v1/documents/..%2Fadmin%3Fx%3D1',
    );
  });
});

describe('authorizeYjsUpgrade', () => {
  const access = fakeAccess(['owner:doc-1']);
  const check = (url: string, authorization?: string) =>
    authorizeYjsUpgrade(url, authorization, jwtSecret, access, mockLogger);

  it('accepts the owner on document-<id>', async () => {
    await expect(check(`/document-doc-1?token=${tokenFor('owner')}`)).resolves.toBe(200);
    await expect(check('/document-doc-1', `Bearer ${tokenFor('owner')}`)).resolves.toBe(
      200,
    );
  });

  it('rejects a valid JWT for a user without access to the document', async () => {
    await expect(check(`/document-doc-1?token=${tokenFor('outsider')}`)).resolves.toBe(
      403,
    );
  });

  it('rejects missing and invalid tokens with 401', async () => {
    await expect(check('/document-doc-1')).resolves.toBe(401);
    await expect(check('/document-doc-1?token=not-a-jwt')).resolves.toBe(401);
    const forged = jwt.sign({ sub: 'owner' }, randomBytes(32).toString('hex'));
    await expect(check(`/document-doc-1?token=${forged}`)).resolves.toBe(401);
  });

  it('rejects rooms that are not document-<id>', async () => {
    const token = tokenFor('owner');
    await expect(check(`/doc-1?token=${token}`)).resolves.toBe(403);
    await expect(check(`/document-?token=${token}`)).resolves.toBe(403);
    await expect(check(`/document-%E0%A4%A?token=${token}`)).resolves.toBe(403);
    await expect(check(`/document-doc-1/x?token=${token}`)).resolves.toBe(403);
  });
});

describe('presence HTTP routes', () => {
  let server: Server;
  let baseUrl: string;
  const awareness = new AwarenessService(mockLogger);

  beforeAll((done) => {
    const app = express();
    const presenceHandler = new PresenceHandler(awareness, mockLogger);
    app.use(
      '/api/v1/collab',
      createPresenceRouter(
        presenceHandler,
        fakeAccess(['owner:doc-1']),
        jwtSecret,
        mockLogger,
      ),
    );
    awareness.addUser('doc-1', 's1', 'owner', 'Owner', 'owner@test.io');
    awareness.addUser('doc-2', 's2', 'other', 'Other', 'other@test.io');
    server = app.listen(0, () => {
      baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}/api/v1/collab`;
      done();
    });
  });

  afterAll((done) => {
    server.close(done);
  });

  it('returns 401 without a JWT', async () => {
    expect((await fetch(`${baseUrl}/documents/doc-1/presence`)).status).toBe(401);
    expect((await fetch(`${baseUrl}/documents`)).status).toBe(401);
    const bad = await fetch(`${baseUrl}/documents/doc-1/presence`, {
      headers: { Authorization: 'Bearer not-a-jwt' },
    });
    expect(bad.status).toBe(401);
  });

  it('returns presence for a user with document access', async () => {
    const res = await fetch(`${baseUrl}/documents/doc-1/presence`, {
      headers: { Authorization: `Bearer ${tokenFor('owner')}` },
    });
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ documentId: 'doc-1', count: 1 });
  });

  it('returns 404 for a user without document access', async () => {
    const res = await fetch(`${baseUrl}/documents/doc-1/presence`, {
      headers: { Authorization: `Bearer ${tokenFor('outsider')}` },
    });
    expect(res.status).toBe(404);
  });

  it('lists only active documents the caller can open', async () => {
    const res = await fetch(`${baseUrl}/documents`, {
      headers: { Authorization: `Bearer ${tokenFor('owner')}` },
    });
    expect(await res.json()).toEqual({
      documents: [{ documentId: 'doc-1', userCount: 1 }],
      count: 1,
    });
  });
});

describe('Socket.IO document authorization', () => {
  let io: SocketIOServer;
  let httpServer: ReturnType<typeof createServer>;
  let manager: CollaborationManager;
  let port: number;
  const clients: ClientSocket[] = [];

  const mockRedis = {
    get: jest.fn().mockResolvedValue(null),
    set: jest.fn().mockResolvedValue(undefined),
    del: jest.fn().mockResolvedValue(undefined),
    lpush: jest.fn().mockResolvedValue(undefined),
    lrange: jest.fn().mockResolvedValue([]),
    ltrim: jest.fn().mockResolvedValue(undefined),
    expire: jest.fn().mockResolvedValue(undefined),
  } as unknown as RedisAdapter;

  beforeAll((done) => {
    httpServer = createServer();
    io = new SocketIOServer(httpServer);
    io.use(createAuthMiddleware(jwtSecret, mockLogger));
    const awareness = new AwarenessService(mockLogger);
    manager = new CollaborationManager({
      io,
      documentStore: new DocumentStore(mockRedis, mockLogger),
      awareness,
      presenceHandler: new PresenceHandler(awareness, mockLogger),
      metrics: new MetricsCollector(),
      logger: mockLogger,
      persistIntervalMs: 60000,
      snapshotIntervalMs: 60000,
      documentAccess: fakeAccess(['alice:doc-1', 'bob:doc-1', 'alice:doc-2']),
    });
    manager.start();
    httpServer.listen(0, () => {
      port = (httpServer.address() as AddressInfo).port;
      done();
    });
  });

  afterEach(() => {
    clients.splice(0).forEach((c) => c.disconnect());
  });

  afterAll((done) => {
    manager.stop();
    io.close();
    httpServer.close(done);
  });

  function connect(userId: string): Promise<ClientSocket> {
    return new Promise((resolve, reject) => {
      const client = clientIO(`http://localhost:${port}`, {
        auth: { token: tokenFor(userId) },
        transports: ['websocket'],
      });
      clients.push(client);
      client.on('connect', () => resolve(client));
      client.on('connect_error', reject);
    });
  }

  function join(client: ClientSocket, documentId: string): Promise<{ success: boolean }> {
    return new Promise((resolve) =>
      client.emit('join-document', { documentId }, resolve),
    );
  }

  function next<T>(client: ClientSocket, event: string, timeoutMs = 2000): Promise<T> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error(`timeout waiting for ${event}`)),
        timeoutMs,
      );
      client.once(event, (data: T) => {
        clearTimeout(timer);
        resolve(data);
      });
    });
  }

  function silent(client: ClientSocket, event: string, ms = 300): Promise<void> {
    return new Promise((resolve, reject) => {
      const onEvent = () => reject(new Error(`unexpected ${event}`));
      client.once(event, onEvent);
      setTimeout(() => {
        client.off(event, onEvent);
        resolve();
      }, ms);
    });
  }

  it('lets a user with document access join and receive state', async () => {
    const alice = await connect('alice');
    const synced = next(alice, 'sync-document');
    expect(await join(alice, 'doc-1')).toMatchObject({ success: true });
    await synced;
  });

  it('refuses join-document for a user without access and sends no document state', async () => {
    const mallory = await connect('mallory');
    const noState = Promise.all([
      silent(mallory, 'sync-document'),
      silent(mallory, 'presence-update'),
    ]);
    expect(await join(mallory, 'doc-1')).toEqual({
      success: false,
      error: 'Access denied',
    });
    await noState;
  });

  it('does not let an unjoined socket push updates or read snapshots/history', async () => {
    const alice = await connect('alice');
    await join(alice, 'doc-1');
    const mallory = await connect('mallory');
    const noRelay = silent(alice, 'document-update');
    mallory.emit('document-update', { documentId: 'doc-1', update: 'AAA=' });
    await noRelay;

    const historyError = next(mallory, 'history-error');
    mallory.emit('request-history', { documentId: 'doc-1' });
    await historyError;
    const snapshotError = next(mallory, 'snapshot-error');
    mallory.emit('request-snapshot', { documentId: 'doc-1' });
    await snapshotError;
  });

  describe('comments', () => {
    const comment = {
      id: 'c-1',
      threadId: 't-1',
      content: 'hi',
      rangeStart: 0,
      rangeEnd: 2,
    };

    async function room(documentId: string): Promise<[ClientSocket, ClientSocket]> {
      const alice = await connect('alice');
      const bob = await connect('bob');
      await join(alice, documentId);
      await join(bob, documentId);
      const added = Promise.all([
        next(bob, 'comment-added'),
        next(alice, 'comment-added'),
      ]);
      alice.emit('comment-add', { documentId, comment });
      await added;
      return [alice, bob];
    }

    it('lets the author update and delete their own comment', async () => {
      const [alice, bob] = await room('doc-1');
      const updated = next(bob, 'comment-updated');
      alice.emit('comment-update', {
        documentId: 'doc-1',
        commentId: 'c-1',
        content: 'edited',
      });
      expect(await updated).toMatchObject({ commentId: 'c-1', content: 'edited' });

      const deleted = next(bob, 'comment-deleted');
      alice.emit('comment-delete', { documentId: 'doc-1', commentId: 'c-1' });
      expect(await deleted).toEqual({ commentId: 'c-1', deletedBy: 'alice' });
    });

    it("rejects another member's update and delete of the comment", async () => {
      const [alice, bob] = await room('doc-1');
      const noChange = Promise.all([
        silent(alice, 'comment-updated'),
        silent(alice, 'comment-deleted'),
      ]);
      const errors = next<{ commentId: string }>(bob, 'comment-error');
      bob.emit('comment-update', {
        documentId: 'doc-1',
        commentId: 'c-1',
        content: 'hijack',
      });
      bob.emit('comment-delete', { documentId: 'doc-1', commentId: 'c-1' });
      expect(await errors).toMatchObject({ commentId: 'c-1' });
      await noChange;

      // the author still owns it afterwards
      const updated = next(bob, 'comment-updated');
      alice.emit('comment-update', {
        documentId: 'doc-1',
        commentId: 'c-1',
        content: 'mine',
      });
      await updated;
    });

    it('does not let another member take over a comment id by re-adding it', async () => {
      const [alice, bob] = await room('doc-1');
      const noAdd = silent(alice, 'comment-added');
      const error = next(bob, 'comment-error');
      bob.emit('comment-add', {
        documentId: 'doc-1',
        comment: { ...comment, content: 'x' },
      });
      await error;
      await noAdd;
    });

    it('rejects update/delete of a comment the server has no record of', async () => {
      const alice = await connect('alice');
      await join(alice, 'doc-2');
      const error = next(alice, 'comment-error');
      alice.emit('comment-delete', { documentId: 'doc-2', commentId: 'unknown' });
      await error;
    });
  });
});
