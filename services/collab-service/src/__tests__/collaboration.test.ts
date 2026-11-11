import { Server as SocketIOServer } from 'socket.io';
import { createServer } from 'http';
import { randomUUID } from 'crypto';
import { io as clientIO, Socket as ClientSocket } from 'socket.io-client';
import jwt from 'jsonwebtoken';
import * as Y from 'yjs';
import { CollaborationManager } from '../handlers/collaboration';
import { DocumentStore } from '../services/document-store';
import { AwarenessService } from '../services/awareness';
import { PresenceHandler } from '../handlers/presence';
import { MetricsCollector } from '../metrics';
import { createAuthMiddleware } from '../middleware/auth';
import { RedisAdapter } from '../services/redis-adapter';
import type { DocumentAccessCheck } from '../services/document-access';

const JWT_SECRET = 'test-secret-key-for-unit-tests';
let PORT: number;

const DOCS = {
  cursor: randomUUID(),
  disc: randomUUID(),
  join: randomUUID(),
  leave: randomUUID(),
  notify: randomUUID(),
  sync: randomUUID(),
  update: randomUUID(),
};

// Mirrors document-service: a document is readable only by the users granted on it.
// The shared fixture documents above are open to every test user.
const documentAcl = new Map<string, Set<string>>();
const openDocuments = new Set<string>(Object.values(DOCS));
const documentAccess: jest.Mocked<DocumentAccessCheck> = {
  canAccess: jest.fn(async (documentId: string, userId: string, token: string) => {
    if (!token) return false;
    if (openDocuments.has(documentId)) return true;
    return documentAcl.get(documentId)?.has(userId) ?? false;
  }),
};

function createToken(payload: Record<string, unknown>): string {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: '1h' }); // nosemgrep: javascript.jsonwebtoken.security.jwt-hardcode.hardcoded-jwt-secret
}

const mockRedis = {
  get: jest.fn().mockResolvedValue(null),
  set: jest.fn().mockResolvedValue(undefined),
  del: jest.fn().mockResolvedValue(undefined),
  hset: jest.fn().mockResolvedValue(undefined),
  hget: jest.fn().mockResolvedValue(null),
  hgetall: jest.fn().mockResolvedValue({}),
  hdel: jest.fn().mockResolvedValue(undefined),
  hincrby: jest.fn().mockResolvedValue(1),
  lpush: jest.fn().mockResolvedValue(undefined),
  lrange: jest.fn().mockResolvedValue([]),
  ltrim: jest.fn().mockResolvedValue(undefined),
  llen: jest.fn().mockResolvedValue(0),
  expire: jest.fn().mockResolvedValue(undefined),
  publish: jest.fn().mockResolvedValue(undefined),
  subscribe: jest.fn().mockResolvedValue(undefined),
  connect: jest.fn().mockResolvedValue(undefined),
  disconnect: jest.fn(),
  ping: jest.fn().mockResolvedValue(true),
} as unknown as jest.Mocked<RedisAdapter>;

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

describe('CollaborationManager', () => {
  let io: SocketIOServer;
  let httpServer: ReturnType<typeof createServer>;
  let manager: CollaborationManager;
  let metrics: MetricsCollector;
  let awareness: AwarenessService;
  let presenceHandler: PresenceHandler;
  let documentStore: DocumentStore;

  beforeAll((done) => {
    httpServer = createServer();
    io = new SocketIOServer(httpServer, {
      cors: { origin: '*' },
    });

    io.use(createAuthMiddleware(JWT_SECRET, mockLogger));

    metrics = new MetricsCollector();
    awareness = new AwarenessService(mockLogger);
    presenceHandler = new PresenceHandler(awareness, mockLogger);
    documentStore = new DocumentStore(mockRedis, mockLogger);

    manager = new CollaborationManager({
      io,
      documentStore,
      awareness,
      presenceHandler,
      documentAccess,
      metrics,
      logger: mockLogger,
      persistIntervalMs: 600000, // long interval so it doesn't fire during tests
      snapshotIntervalMs: 600000,
    });
    manager.start();

    httpServer.listen(0, () => {
      const addr = httpServer.address();
      PORT = typeof addr === 'object' && addr ? addr.port : 0;
      done();
    });
  }, 15000);

  afterAll((done) => {
    manager.stop();
    io.close();
    httpServer.close(done);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  function connectClient(userId: string, displayName: string): Promise<ClientSocket> {
    return new Promise((resolve, reject) => {
      const token = createToken({
        sub: userId,
        name: displayName,
        email: `${userId}@test.com`,
        roles: ['user'],
      });

      const client = clientIO(`http://localhost:${PORT}`, {
        auth: { token },
        transports: ['websocket'],
      });

      client.on('connect', () => resolve(client));
      client.on('connect_error', (err) => reject(err));

      setTimeout(() => reject(new Error('Connection timeout')), 5000);
    });
  }

  describe('Authentication', () => {
    it('should reject connections without a token', (done) => {
      const client = clientIO(`http://localhost:${PORT}`, {
        auth: {},
        transports: ['websocket'],
      });

      client.on('connect_error', (err) => {
        expect(err.message).toContain('Authentication required');
        client.disconnect();
        done();
      });
    });

    it('should reject connections with an invalid token', (done) => {
      const client = clientIO(`http://localhost:${PORT}`, {
        auth: { token: 'invalid-token-value' },
        transports: ['websocket'],
      });

      client.on('connect_error', (err) => {
        expect(err.message).toContain('Invalid or expired token');
        client.disconnect();
        done();
      });
    });

    it('should accept connections with a valid token', async () => {
      const client = await connectClient('user-auth-test', 'Test User');
      expect(client.connected).toBe(true);
      client.disconnect();
    });
  });

  describe('Document Joining', () => {
    it('should allow a user to join a document room', async () => {
      const client = await connectClient('user-join-1', 'Alice');

      const response = await new Promise<{ success: boolean }>((resolve) => {
        client.emit(
          'join-document',
          { documentId: DOCS.join },
          (res: { success: boolean }) => resolve(res),
        );
      });

      expect(response.success).toBe(true);
      client.disconnect();
    });

    it('should sync document state to joining client', async () => {
      const client = await connectClient('user-sync-1', 'Bob');

      const syncPromise = new Promise<{ documentId: string; state: string }>(
        (resolve) => {
          client.on('sync-document', (data) => resolve(data));
        },
      );

      client.emit('join-document', { documentId: DOCS.sync }, () => {});

      const syncData = await syncPromise;
      expect(syncData.documentId).toBe(DOCS.sync);
      expect(syncData.state).toBeDefined();

      client.disconnect();
    });

    it('should notify other users when someone joins', async () => {
      const client1 = await connectClient('user-notify-1', 'Alice');
      const client2 = await connectClient('user-notify-2', 'Bob');

      // Client 1 joins first
      await new Promise<void>((resolve) => {
        client1.emit('join-document', { documentId: DOCS.notify }, () => resolve());
      });

      // Listen for join notification on client 1
      const joinPromise = new Promise<{ userId: string; displayName: string }>(
        (resolve) => {
          client1.on('user-joined', (data) => resolve(data));
        },
      );

      // Client 2 joins
      client2.emit('join-document', { documentId: DOCS.notify }, () => {});

      const joinData = await joinPromise;
      expect(joinData.userId).toBe('user-notify-2');
      expect(joinData.displayName).toBe('Bob');

      client1.disconnect();
      client2.disconnect();
    });
  });

  describe('Document Updates', () => {
    it('should broadcast document updates to other clients', async () => {
      const client1 = await connectClient('user-update-1', 'Alice');
      const client2 = await connectClient('user-update-2', 'Bob');

      // Both join the same document
      await Promise.all([
        new Promise<void>((resolve) => {
          client1.emit('join-document', { documentId: DOCS.update }, () => resolve());
        }),
        new Promise<void>((resolve) => {
          client2.emit('join-document', { documentId: DOCS.update }, () => resolve());
        }),
      ]);

      // Wait for sync to complete
      await new Promise((r) => setTimeout(r, 100));

      // Listen for update on client 2
      const updatePromise = new Promise<{
        documentId: string;
        update: string;
      }>((resolve) => {
        client2.on('document-update', (data) => resolve(data));
      });

      // Create a valid Yjs update
      const tempDoc = new Y.Doc();
      const text = tempDoc.getText('content');
      text.insert(0, 'Hello');
      const validUpdate = Y.encodeStateAsUpdate(tempDoc);
      const encodedUpdate = Buffer.from(validUpdate).toString('base64');

      client1.emit('document-update', {
        documentId: DOCS.update,
        update: encodedUpdate,
      });

      const updateData = await updatePromise;
      expect(updateData.documentId).toBe(DOCS.update);
      expect(updateData.update).toBe(encodedUpdate);

      client1.disconnect();
      client2.disconnect();
    });
  });

  describe('Cursor Updates', () => {
    it('should broadcast cursor updates to other clients', async () => {
      const client1 = await connectClient('user-cursor-1', 'Alice');
      const client2 = await connectClient('user-cursor-2', 'Bob');

      await Promise.all([
        new Promise<void>((resolve) => {
          client1.emit('join-document', { documentId: DOCS.cursor }, () => resolve());
        }),
        new Promise<void>((resolve) => {
          client2.emit('join-document', { documentId: DOCS.cursor }, () => resolve());
        }),
      ]);

      await new Promise((r) => setTimeout(r, 100));

      const cursorPromise = new Promise<{
        userId: string;
        cursor: { index: number; length: number };
      }>((resolve) => {
        client2.on('cursor-update', (data) => resolve(data));
      });

      client1.emit('cursor-update', {
        documentId: DOCS.cursor,
        cursor: { index: 42, length: 0 },
        selection: null,
      });

      const cursorData = await cursorPromise;
      expect(cursorData.userId).toBe('user-cursor-1');
      expect(cursorData.cursor).toEqual({ index: 42, length: 0 });

      client1.disconnect();
      client2.disconnect();
    });
  });

  describe('Disconnect Handling', () => {
    it('should notify others when a user disconnects', async () => {
      const client1 = await connectClient('user-disc-1', 'Alice');
      const client2 = await connectClient('user-disc-2', 'Bob');

      await Promise.all([
        new Promise<void>((resolve) => {
          client1.emit('join-document', { documentId: DOCS.disc }, () => resolve());
        }),
        new Promise<void>((resolve) => {
          client2.emit('join-document', { documentId: DOCS.disc }, () => resolve());
        }),
      ]);

      await new Promise((r) => setTimeout(r, 100));

      const leftPromise = new Promise<{ userId: string }>((resolve) => {
        client1.on('user-left', (data) => resolve(data));
      });

      client2.disconnect();

      const leftData = await leftPromise;
      expect(leftData.userId).toBe('user-disc-2');

      client1.disconnect();
    });
  });

  describe('Leave Document', () => {
    it('should allow a user to leave a document', async () => {
      const client1 = await connectClient('user-leave-1', 'Alice');
      const client2 = await connectClient('user-leave-2', 'Bob');

      await Promise.all([
        new Promise<void>((resolve) => {
          client1.emit('join-document', { documentId: DOCS.leave }, () => resolve());
        }),
        new Promise<void>((resolve) => {
          client2.emit('join-document', { documentId: DOCS.leave }, () => resolve());
        }),
      ]);

      await new Promise((r) => setTimeout(r, 100));

      const leftPromise = new Promise<{ socketId: string }>((resolve) => {
        client1.on('user-left', (data) => resolve(data));
      });

      client2.emit('leave-document', { documentId: DOCS.leave });

      const leftData = await leftPromise;
      expect(leftData.socketId).toBeDefined();

      client1.disconnect();
      client2.disconnect();
    });
  });

  describe('Document Authorization', () => {
    function join(
      client: ClientSocket,
      documentId: unknown,
    ): Promise<{ success: boolean; error?: string }> {
      return new Promise((resolve) => {
        client.emit('join-document', { documentId }, resolve);
      });
    }

    function privateDocument(ownerId: string): string {
      const documentId = randomUUID();
      documentAcl.set(documentId, new Set([ownerId]));
      return documentId;
    }

    it("should refuse to let user B join user A's document", async () => {
      const aliceDoc = privateDocument('authz-alice-1');
      const mallory = await connectClient('authz-mallory-1', 'Mallory');
      const synced = jest.fn();
      mallory.on('sync-document', synced);

      const response = await join(mallory, aliceDoc);
      await new Promise((r) => setTimeout(r, 50));

      expect(response).toEqual({ success: false, error: 'Access denied' });
      expect(synced).not.toHaveBeenCalled();
      expect(manager.getDocument(aliceDoc)).toBeUndefined();
      expect(documentAccess.canAccess).toHaveBeenCalledWith(
        aliceDoc,
        'authz-mallory-1',
        expect.any(String),
      );
      mallory.disconnect();
    });

    it('should let the owner join their own document', async () => {
      const aliceDoc = privateDocument('authz-alice-2');
      const alice = await connectClient('authz-alice-2', 'Alice');

      await expect(join(alice, aliceDoc)).resolves.toEqual({ success: true });
      alice.disconnect();
    });

    it('should reject a malformed document id without asking document-service', async () => {
      const client = await connectClient('authz-bad-id', 'Eve');

      await expect(join(client, '../../etc')).resolves.toEqual({
        success: false,
        error: 'Invalid document id',
      });
      expect(documentAccess.canAccess).not.toHaveBeenCalled();
      client.disconnect();
    });

    it('should reject events for a document the socket has not joined', async () => {
      const aliceDoc = privateDocument('authz-alice-3');
      const malloryDoc = privateDocument('authz-mallory-3');
      const alice = await connectClient('authz-alice-3', 'Alice');
      const mallory = await connectClient('authz-mallory-3', 'Mallory');

      await expect(join(alice, aliceDoc)).resolves.toEqual({ success: true });
      await expect(join(mallory, malloryDoc)).resolves.toEqual({ success: true });

      const aliceReceived = jest.fn();
      alice.on('document-update', aliceReceived);
      alice.on('comment-added', aliceReceived);
      alice.on('comment-deleted', aliceReceived);
      const historyReceived = jest.fn();
      mallory.on('document-history', historyReceived);
      const rejected: Array<{ event: string; documentId: string }> = [];
      mallory.on('collab-error', (err) => rejected.push(err));

      const tempDoc = new Y.Doc();
      tempDoc.getText('content').insert(0, 'pwned');
      const update = Buffer.from(Y.encodeStateAsUpdate(tempDoc)).toString('base64');

      mallory.emit('document-update', { documentId: aliceDoc, update });
      mallory.emit('comment-add', {
        documentId: aliceDoc,
        comment: { id: 'c1', threadId: 't1', content: 'hi', rangeStart: 0, rangeEnd: 1 },
      });
      mallory.emit('comment-delete', { documentId: aliceDoc, commentId: 'c1' });
      mallory.emit('request-snapshot', { documentId: aliceDoc });
      mallory.emit('request-history', { documentId: aliceDoc });
      mallory.emit('leave-document', { documentId: aliceDoc });
      await new Promise((r) => setTimeout(r, 150));

      expect(rejected.map((r) => r.event)).toEqual([
        'document-update',
        'comment-add',
        'comment-delete',
        'request-snapshot',
        'request-history',
        'leave-document',
      ]);
      expect(rejected.every((r) => r.documentId === aliceDoc)).toBe(true);
      expect(aliceReceived).not.toHaveBeenCalled();
      expect(historyReceived).not.toHaveBeenCalled();
      expect(manager.getDocument(aliceDoc)?.getText('content').toString()).toBe('');

      alice.disconnect();
      mallory.disconnect();
    });

    it('should keep a socket on its current document when a switch is denied', async () => {
      const malloryDoc = privateDocument('authz-mallory-4');
      const aliceDoc = privateDocument('authz-alice-4');
      const mallory = await connectClient('authz-mallory-4', 'Mallory');

      await expect(join(mallory, malloryDoc)).resolves.toEqual({ success: true });
      await expect(join(mallory, aliceDoc)).resolves.toEqual({
        success: false,
        error: 'Access denied',
      });

      const history = new Promise<{ documentId: string }>((resolve) => {
        mallory.on('document-history', resolve);
      });
      mallory.emit('request-history', { documentId: malloryDoc });
      await expect(history).resolves.toMatchObject({ documentId: malloryDoc });

      mallory.disconnect();
    });
  });
});
