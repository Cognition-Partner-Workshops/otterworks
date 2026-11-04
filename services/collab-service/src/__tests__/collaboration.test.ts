import { Server as SocketIOServer } from 'socket.io';
import { createServer } from 'http';
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
import type { DocumentAccessPolicy } from '../services/document-access';

const JWT_SECRET = 'test-secret-key-for-unit-tests';
let PORT: number;

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

// Documents listed here may only be opened by their owner; any other document is
// treated as accessible so the existing flow tests keep exercising the happy path.
const documentOwners = new Map<string, string>([
  ['alice-private-doc', 'user-alice'],
  ['alice-private-doc-2', 'user-alice'],
]);

const accessPolicy: jest.Mocked<DocumentAccessPolicy> = {
  canAccess: jest.fn(async (documentId, principal) => {
    if (!principal.token) return false;
    const owner = documentOwners.get(documentId);
    return owner === undefined || owner === principal.userId;
  }),
};

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
      accessPolicy,
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
          { documentId: 'doc-join-test' },
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

      client.emit('join-document', { documentId: 'doc-sync-test' }, () => {});

      const syncData = await syncPromise;
      expect(syncData.documentId).toBe('doc-sync-test');
      expect(syncData.state).toBeDefined();

      client.disconnect();
    });

    it('should notify other users when someone joins', async () => {
      const client1 = await connectClient('user-notify-1', 'Alice');
      const client2 = await connectClient('user-notify-2', 'Bob');

      // Client 1 joins first
      await new Promise<void>((resolve) => {
        client1.emit('join-document', { documentId: 'doc-notify-test' }, () => resolve());
      });

      // Listen for join notification on client 1
      const joinPromise = new Promise<{ userId: string; displayName: string }>(
        (resolve) => {
          client1.on('user-joined', (data) => resolve(data));
        },
      );

      // Client 2 joins
      client2.emit('join-document', { documentId: 'doc-notify-test' }, () => {});

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
          client1.emit('join-document', { documentId: 'doc-update-test' }, () =>
            resolve(),
          );
        }),
        new Promise<void>((resolve) => {
          client2.emit('join-document', { documentId: 'doc-update-test' }, () =>
            resolve(),
          );
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
        documentId: 'doc-update-test',
        update: encodedUpdate,
      });

      const updateData = await updatePromise;
      expect(updateData.documentId).toBe('doc-update-test');
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
          client1.emit('join-document', { documentId: 'doc-cursor-test' }, () =>
            resolve(),
          );
        }),
        new Promise<void>((resolve) => {
          client2.emit('join-document', { documentId: 'doc-cursor-test' }, () =>
            resolve(),
          );
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
        documentId: 'doc-cursor-test',
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
          client1.emit('join-document', { documentId: 'doc-disc-test' }, () => resolve());
        }),
        new Promise<void>((resolve) => {
          client2.emit('join-document', { documentId: 'doc-disc-test' }, () => resolve());
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
          client1.emit('join-document', { documentId: 'doc-leave-test' }, () =>
            resolve(),
          );
        }),
        new Promise<void>((resolve) => {
          client2.emit('join-document', { documentId: 'doc-leave-test' }, () =>
            resolve(),
          );
        }),
      ]);

      await new Promise((r) => setTimeout(r, 100));

      const leftPromise = new Promise<{ socketId: string }>((resolve) => {
        client1.on('user-left', (data) => resolve(data));
      });

      client2.emit('leave-document', { documentId: 'doc-leave-test' });

      const leftData = await leftPromise;
      expect(leftData.socketId).toBeDefined();

      client1.disconnect();
      client2.disconnect();
    });
  });
  describe('Document Authorization', () => {
    function join(
      client: ClientSocket,
      documentId: string,
    ): Promise<{ success: boolean; error?: string }> {
      return new Promise((resolve) => {
        client.emit('join-document', { documentId }, resolve);
      });
    }

    function encodeText(value: string): string {
      const tempDoc = new Y.Doc();
      tempDoc.getText('content').insert(0, value);
      return Buffer.from(Y.encodeStateAsUpdate(tempDoc)).toString('base64');
    }

    it('checks access with the caller identity and token', async () => {
      const alice = await connectClient('user-alice', 'Alice');
      const response = await join(alice, 'alice-private-doc');

      expect(response.success).toBe(true);
      expect(accessPolicy.canAccess).toHaveBeenCalledWith(
        'alice-private-doc',
        expect.objectContaining({ userId: 'user-alice', token: expect.any(String) }),
      );
      expect(accessPolicy.canAccess.mock.calls[0][1].token).not.toBe('');
      alice.disconnect();
    });

    it('rejects join-document for a document the caller cannot access', async () => {
      const mallory = await connectClient('user-mallory', 'Mallory');
      const synced = jest.fn();
      mallory.on('sync-document', synced);

      const response = await join(mallory, 'alice-private-doc');
      await new Promise((r) => setTimeout(r, 100));

      expect(response).toEqual({ success: false, error: 'Access denied' });
      expect(synced).not.toHaveBeenCalled();
      expect(awareness.getDocumentUsers('alice-private-doc')).toHaveLength(0);
      mallory.disconnect();
    });

    it('rejects join-document with an invalid document id without an access check', async () => {
      const client = await connectClient('user-invalid-id', 'Eve');
      const response = await join(client, '../../etc/passwd');

      expect(response).toEqual({ success: false, error: 'Invalid document id' });
      expect(accessPolicy.canAccess).not.toHaveBeenCalled();
      client.disconnect();
    });

    it('denies join-document when the access check throws', async () => {
      accessPolicy.canAccess.mockRejectedValueOnce(new Error('document-service down'));
      const client = await connectClient('user-alice', 'Alice');
      const response = await join(client, 'alice-private-doc');

      expect(response).toEqual({ success: false, error: 'Access denied' });
      client.disconnect();
    });

    it('ignores updates, comments and cursors from sockets that have not joined', async () => {
      const alice = await connectClient('user-alice', 'Alice');
      const mallory = await connectClient('user-mallory', 'Mallory');
      expect((await join(alice, 'alice-private-doc-2')).success).toBe(true);
      expect((await join(mallory, 'alice-private-doc-2')).success).toBe(false);

      const aliceReceived = jest.fn();
      alice.on('document-update', aliceReceived);
      alice.on('comment-added', aliceReceived);
      alice.on('comment-deleted', aliceReceived);
      alice.on('cursor-update', aliceReceived);
      alice.on('typing-indicator', aliceReceived);

      const updateError = new Promise<{ error: string }>((resolve) => {
        mallory.on('document-update-error', resolve);
      });

      mallory.emit('document-update', {
        documentId: 'alice-private-doc-2',
        update: encodeText('TAMPERED'),
      });
      mallory.emit('comment-add', {
        documentId: 'alice-private-doc-2',
        comment: {
          id: 'c1',
          threadId: 't1',
          content: 'spam',
          rangeStart: 0,
          rangeEnd: 1,
        },
      });
      mallory.emit('comment-delete', {
        documentId: 'alice-private-doc-2',
        commentId: 'c1',
      });
      mallory.emit('cursor-update', {
        documentId: 'alice-private-doc-2',
        cursor: { index: 0, length: 0 },
        selection: null,
      });
      mallory.emit('typing-indicator', {
        documentId: 'alice-private-doc-2',
        isTyping: true,
      });

      expect((await updateError).error).toBe('Not joined to document');
      await new Promise((r) => setTimeout(r, 150));

      expect(aliceReceived).not.toHaveBeenCalled();
      const doc = manager.getDocument('alice-private-doc-2');
      expect(doc?.getText('content').toString()).toBe('');

      alice.disconnect();
      mallory.disconnect();
    });

    it('rejects snapshot and history requests from sockets that have not joined', async () => {
      const mallory = await connectClient('user-mallory', 'Mallory');

      const historyError = new Promise<{ error: string }>((resolve) => {
        mallory.on('history-error', resolve);
      });
      const snapshotError = new Promise<{ error: string }>((resolve) => {
        mallory.on('snapshot-error', resolve);
      });
      const history = jest.fn();
      mallory.on('document-history', history);

      mallory.emit('request-history', { documentId: 'alice-private-doc' });
      mallory.emit('request-snapshot', { documentId: 'alice-private-doc' });

      expect((await historyError).error).toBe('Not joined to document');
      expect((await snapshotError).error).toBe('Not joined to document');
      expect(history).not.toHaveBeenCalled();
      expect(mockRedis.lrange).not.toHaveBeenCalled();
      mallory.disconnect();
    });

    it('does not expose email addresses in presence', async () => {
      const alice = await connectClient('user-alice', 'Alice');
      const presenceUpdate = new Promise<{ users: Array<Record<string, unknown>> }>(
        (resolve) => {
          alice.on('presence-update', resolve);
        },
      );
      expect((await join(alice, 'alice-private-doc')).success).toBe(true);

      const broadcast = await presenceUpdate;
      expect(broadcast.users).toHaveLength(1);
      expect(broadcast.users[0]).not.toHaveProperty('email');

      const presence = presenceHandler.getDocumentPresence('alice-private-doc');
      expect(presence.users[0].userId).toBe('user-alice');
      expect(presence.users[0]).not.toHaveProperty('email');
      alice.disconnect();
    });
  });
});
