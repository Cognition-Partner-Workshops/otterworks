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
import type { DocumentAccessRequest } from '../services/document-access';

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

// Documents listed here are only accessible to the listed users (owner + shared
// collaborators); every other document id is treated as accessible so the
// pre-existing behaviour tests keep exercising the happy path.
const documentAcl: Record<string, string[]> = {
  'doc-victim-private': ['user-victim', 'user-collaborator'],
};

const documentAccess = {
  canAccess: jest.fn(async ({ documentId, userId }: DocumentAccessRequest) => {
    const allowed = documentAcl[documentId];
    return allowed ? allowed.includes(userId) : true;
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
      metrics,
      logger: mockLogger,
      documentAccess,
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
  describe('Per-document authorization', () => {
    const victimDoc = 'doc-victim-private';

    function join(
      client: ClientSocket,
      documentId: unknown,
    ): Promise<{ success: boolean; error?: string }> {
      return new Promise((resolve) => {
        client.emit('join-document', { documentId }, resolve);
      });
    }

    function encodedTextUpdate(content: string): string {
      const tempDoc = new Y.Doc();
      tempDoc.getText('content').insert(0, content);
      return Buffer.from(Y.encodeStateAsUpdate(tempDoc)).toString('base64');
    }

    function nextEvent<T>(client: ClientSocket, event: string): Promise<T> {
      return new Promise((resolve) => client.once(event, resolve));
    }

    function expectNoEvent(client: ClientSocket, event: string, ms = 200): Promise<void> {
      return new Promise((resolve, reject) => {
        const handler = () => reject(new Error(`unexpected ${event}`));
        client.once(event, handler);
        setTimeout(() => {
          client.off(event, handler);
          resolve();
        }, ms);
      });
    }

    it('passes the handshake token and user id to the access check', async () => {
      const client = await connectClient('user-victim', 'Victim');

      await join(client, victimDoc);

      const token = (client.auth as { token: string }).token;
      expect(documentAccess.canAccess).toHaveBeenCalledWith({
        documentId: victimDoc,
        userId: 'user-victim',
        token,
      });
      client.disconnect();
    });

    it('rejects join-document for a document the user cannot access', async () => {
      const victim = await connectClient('user-victim', 'Victim');
      const attacker = await connectClient('user-attacker', 'Mallory');
      expect((await join(victim, victimDoc)).success).toBe(true);

      const noSync = expectNoEvent(attacker, 'sync-document');
      const noJoinBroadcast = expectNoEvent(victim, 'user-joined');
      const response = await join(attacker, victimDoc);

      expect(response).toEqual({ success: false, error: 'Access denied' });
      await Promise.all([noSync, noJoinBroadcast]);
      expect(presenceHandler.getDocumentPresence(victimDoc).users).toHaveLength(1);

      victim.disconnect();
      attacker.disconnect();
    });

    it('rejects document-update for a document the user never joined', async () => {
      const victim = await connectClient('user-victim', 'Victim');
      const attacker = await connectClient('user-attacker', 'Mallory');
      expect((await join(victim, victimDoc)).success).toBe(true);
      const saveSpy = jest.spyOn(documentStore, 'saveDocumentState');
      const before = Y.encodeStateAsUpdate(manager.getDocument(victimDoc)!);

      const errorPromise = nextEvent<{ documentId: string; error: string }>(
        attacker,
        'document-update-error',
      );
      const noBroadcast = expectNoEvent(victim, 'document-update');
      attacker.emit('document-update', {
        documentId: victimDoc,
        update: encodedTextUpdate('tampered'),
      });

      expect(await errorPromise).toEqual({
        documentId: victimDoc,
        error: 'Access denied',
      });
      await noBroadcast;
      expect(Y.encodeStateAsUpdate(manager.getDocument(victimDoc)!)).toEqual(before);
      expect(saveSpy).not.toHaveBeenCalled();

      saveSpy.mockRestore();
      victim.disconnect();
      attacker.disconnect();
    });

    it('rejects document-update after a denied join attempt', async () => {
      const victim = await connectClient('user-victim', 'Victim');
      const attacker = await connectClient('user-attacker', 'Mallory');
      expect((await join(victim, victimDoc)).success).toBe(true);
      expect((await join(attacker, 'doc-attacker-own')).success).toBe(true);
      expect((await join(attacker, victimDoc)).success).toBe(false);

      const errorPromise = nextEvent<{ error: string }>(
        attacker,
        'document-update-error',
      );
      const noBroadcast = expectNoEvent(victim, 'document-update');
      attacker.emit('document-update', {
        documentId: victimDoc,
        update: encodedTextUpdate('tampered'),
      });

      expect((await errorPromise).error).toBe('Access denied');
      await noBroadcast;
      expect(manager.getDocument(victimDoc)!.getText('content').toString()).toBe('');

      victim.disconnect();
      attacker.disconnect();
    });

    it('rejects document-update once the user has left the document', async () => {
      const client = await connectClient('user-victim', 'Victim');
      const observer = await connectClient('user-collaborator', 'Carol');
      expect((await join(client, victimDoc)).success).toBe(true);
      expect((await join(observer, victimDoc)).success).toBe(true);

      client.emit('leave-document', { documentId: victimDoc });
      await new Promise((r) => setTimeout(r, 100));

      const errorPromise = nextEvent<{ error: string }>(client, 'document-update-error');
      client.emit('document-update', {
        documentId: victimDoc,
        update: encodedTextUpdate('after-leave'),
      });
      expect((await errorPromise).error).toBe('Access denied');

      client.disconnect();
      observer.disconnect();
    });

    it('rejects request-history and request-snapshot for unauthorized documents', async () => {
      const attacker = await connectClient('user-attacker', 'Mallory');
      const getSnapshotsSpy = jest.spyOn(documentStore, 'getSnapshots');

      const historyError = nextEvent<{ error: string }>(attacker, 'history-error');
      const noHistory = expectNoEvent(attacker, 'document-history');
      attacker.emit('request-history', { documentId: victimDoc });
      expect((await historyError).error).toBe('Access denied');
      await noHistory;
      expect(getSnapshotsSpy).not.toHaveBeenCalled();

      const snapshotError = nextEvent<{ error: string }>(attacker, 'snapshot-error');
      attacker.emit('request-snapshot', { documentId: victimDoc, label: 'x' });
      expect((await snapshotError).error).toBe('Access denied');

      getSnapshotsSpy.mockRestore();
      attacker.disconnect();
    });

    it('drops comment, cursor and typing events for unauthorized documents', async () => {
      const victim = await connectClient('user-victim', 'Victim');
      const attacker = await connectClient('user-attacker', 'Mallory');
      expect((await join(victim, victimDoc)).success).toBe(true);

      const silent = Promise.all([
        expectNoEvent(victim, 'comment-added'),
        expectNoEvent(victim, 'comment-updated'),
        expectNoEvent(victim, 'comment-deleted'),
        expectNoEvent(attacker, 'comment-added'),
        expectNoEvent(victim, 'typing-indicator'),
      ]);
      attacker.emit('comment-add', {
        documentId: victimDoc,
        comment: {
          id: 'c1',
          threadId: 't1',
          content: 'spam',
          rangeStart: 0,
          rangeEnd: 1,
        },
      });
      attacker.emit('comment-update', {
        documentId: victimDoc,
        commentId: 'c1',
        content: 'x',
      });
      attacker.emit('comment-delete', { documentId: victimDoc, commentId: 'c1' });
      attacker.emit('typing-indicator', { documentId: victimDoc, isTyping: true });
      await silent;

      victim.disconnect();
      attacker.disconnect();
    });

    it('rejects invalid document ids without calling document-service', async () => {
      const client = await connectClient('user-victim', 'Victim');

      expect(await join(client, '../admin')).toEqual({
        success: false,
        error: 'Invalid document id',
      });
      expect(await join(client, { $ne: null })).toEqual({
        success: false,
        error: 'Invalid document id',
      });
      expect(documentAccess.canAccess).not.toHaveBeenCalled();

      client.disconnect();
    });

    it('lets an authorized collaborator join, receive state and edit', async () => {
      const owner = await connectClient('user-victim', 'Victim');
      const collaborator = await connectClient('user-collaborator', 'Carol');
      expect((await join(owner, victimDoc)).success).toBe(true);

      const syncPromise = nextEvent<{ documentId: string }>(
        collaborator,
        'sync-document',
      );
      expect((await join(collaborator, victimDoc)).success).toBe(true);
      expect((await syncPromise).documentId).toBe(victimDoc);

      const update = encodedTextUpdate('shared edit');
      const received = nextEvent<{ update: string }>(owner, 'document-update');
      collaborator.emit('document-update', { documentId: victimDoc, update });
      expect((await received).update).toBe(update);
      expect(manager.getDocument(victimDoc)!.getText('content').toString()).toBe(
        'shared edit',
      );

      owner.disconnect();
      collaborator.disconnect();
    });
  });
});
