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
import type { DocumentAccessChecker } from '../services/document-access';

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

// `private-<ownerId>-*` documents are visible only to their owner,
// `shared-<ownerId>-*` documents are editable by anyone but owned by <ownerId>,
// and every other document id is owned by whoever asks.
const documentAccess: DocumentAccessChecker = {
  check: jest.fn(async (documentId: string, user: { userId: string }) => {
    const match = /^(private|shared)-([^-]+)-/.exec(documentId);
    if (!match) return { isOwner: true, canEdit: true };
    const isOwner = match[2] === user.userId;
    if (match[1] === 'private' && !isOwner) return null;
    return { isOwner, canEdit: true };
  }),
};

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
      documentAccess,
      awareness,
      presenceHandler,
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

  describe('Document Authorization', () => {
    function join(client: ClientSocket, documentId: string) {
      return new Promise<{ success: boolean; error?: string }>((resolve) => {
        client.emit('join-document', { documentId }, resolve);
      });
    }

    function expectNoEvent(client: ClientSocket, event: string, ms = 300) {
      return new Promise<void>((resolve, reject) => {
        const onEvent = () => reject(new Error(`unexpected ${event}`));
        client.once(event, onEvent);
        setTimeout(() => {
          client.off(event, onEvent);
          resolve();
        }, ms);
      });
    }

    it('should ask document-service with the caller token and deny the join when it says no', async () => {
      const owner = await connectClient('alice', 'Alice');
      const outsider = await connectClient('mallory', 'Mallory');
      const documentId = 'private-alice-authz';

      expect(await join(owner, documentId)).toEqual({ success: true });
      expect(documentAccess.check).toHaveBeenCalledWith(
        documentId,
        expect.objectContaining({ userId: 'alice' }),
        expect.any(String),
      );

      const denied = new Promise((resolve) => outsider.once('access-denied', resolve));
      const synced = expectNoEvent(outsider, 'sync-document');
      expect(await join(outsider, documentId)).toEqual({
        success: false,
        error: 'Access denied',
      });
      await expect(denied).resolves.toEqual({ event: 'join-document', documentId });
      await synced;
      expect(presenceHandler.getDocumentPresence(documentId).count).toBe(1);

      owner.disconnect();
      outsider.disconnect();
    });

    it('should drop updates, history and comments from sockets that have not joined the room', async () => {
      const owner = await connectClient('alice', 'Alice');
      const outsider = await connectClient('mallory', 'Mallory');
      const documentId = 'private-alice-events';
      await join(owner, documentId);
      await join(outsider, 'doc-somewhere-else');

      const tempDoc = new Y.Doc();
      tempDoc.getText('content').insert(0, 'tampered');
      const update = Buffer.from(Y.encodeStateAsUpdate(tempDoc)).toString('base64');

      const ownerSawUpdate = expectNoEvent(owner, 'document-update');
      const ownerSawComment = expectNoEvent(owner, 'comment-added');
      const updateError = new Promise((resolve) =>
        outsider.once('document-update-error', resolve),
      );
      const historyError = new Promise((resolve) =>
        outsider.once('history-error', resolve),
      );

      outsider.emit('document-update', { documentId, update });
      outsider.emit('request-history', { documentId });
      outsider.emit('comment-add', {
        documentId,
        comment: { id: 'c1', threadId: 't1', content: 'hi', rangeStart: 0, rangeEnd: 1 },
      });
      outsider.emit('cursor-update', {
        documentId,
        cursor: { line: 0, column: 0 },
        selection: null,
      });

      await expect(updateError).resolves.toEqual({ documentId, error: 'Access denied' });
      await expect(historyError).resolves.toEqual({ documentId, error: 'Access denied' });
      await ownerSawUpdate;
      await ownerSawComment;
      expect(mockRedis.lrange).not.toHaveBeenCalled();
      expect(Y.encodeStateAsUpdate(manager.getDocument(documentId)!)).not.toEqual(
        Y.encodeStateAsUpdate(tempDoc),
      );

      owner.disconnect();
      outsider.disconnect();
    });

    it('should only let the author or the owner change a comment', async () => {
      const alice = await connectClient('alice', 'Alice');
      const bob = await connectClient('bob', 'Bob');
      const documentId = 'shared-alice-comments';
      await join(alice, documentId);
      await join(bob, documentId);
      await new Promise((r) => setTimeout(r, 50));

      const added = new Promise((resolve) => alice.once('comment-added', resolve));
      bob.emit('comment-add', {
        documentId,
        comment: {
          id: 'c-bob',
          threadId: 't1',
          content: 'mine',
          rangeStart: 0,
          rangeEnd: 1,
        },
      });
      await added;

      // Bob is neither the author of c-unknown nor the owner, so the delete is refused.
      const denied = new Promise((resolve) => bob.once('access-denied', resolve));
      const aliceSawDelete = expectNoEvent(alice, 'comment-deleted');
      bob.emit('comment-delete', { documentId, commentId: 'c-unknown' });
      await expect(denied).resolves.toEqual({
        event: 'comment-delete',
        documentId,
        commentId: 'c-unknown',
      });
      await aliceSawDelete;

      const updated = new Promise((resolve) => alice.once('comment-updated', resolve));
      bob.emit('comment-update', { documentId, commentId: 'c-bob', content: 'edited' });
      await expect(updated).resolves.toEqual(
        expect.objectContaining({ commentId: 'c-bob', content: 'edited' }),
      );

      const deleted = new Promise((resolve) => bob.once('comment-deleted', resolve));
      alice.emit('comment-delete', { documentId, commentId: 'c-bob' });
      await expect(deleted).resolves.toEqual(
        expect.objectContaining({ commentId: 'c-bob' }),
      );

      alice.disconnect();
      bob.disconnect();
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
});
