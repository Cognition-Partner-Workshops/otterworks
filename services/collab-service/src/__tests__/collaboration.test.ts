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
import {
  DocumentAccessError,
  type AccessRequest,
  type DocumentAccessChecker,
  type DocumentPermission,
} from '../services/document-access';

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

/** Grants are keyed `documentId:userId`; anything not granted is denied, as document-service would. */
class FakeAccessChecker implements DocumentAccessChecker {
  grants = new Map<string, DocumentPermission>();
  failNext = false;
  requests: AccessRequest[] = [];

  allow(
    documentId: string,
    userId: string,
    permission: DocumentPermission = 'edit',
  ): void {
    this.grants.set(`${documentId}:${userId}`, permission);
  }

  async checkAccess(request: AccessRequest): Promise<DocumentPermission | null> {
    this.requests.push(request);
    if (this.failNext) {
      this.failNext = false;
      throw new DocumentAccessError('document-service unreachable');
    }
    return this.grants.get(`${request.documentId}:${request.user.userId}`) ?? null;
  }
}

function waitFor(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function joinDocument(
  client: ClientSocket,
  documentId: string,
  shareToken?: string,
): Promise<{ success: boolean; error?: string }> {
  return new Promise((resolve) => {
    client.emit(
      'join-document',
      { documentId, shareToken },
      (res: { success: boolean }) => resolve(res),
    );
  });
}

function validUpdate(text: string): string {
  const tempDoc = new Y.Doc();
  tempDoc.getText('content').insert(0, text);
  return Buffer.from(Y.encodeStateAsUpdate(tempDoc)).toString('base64');
}

describe('CollaborationManager', () => {
  let io: SocketIOServer;
  let httpServer: ReturnType<typeof createServer>;
  let manager: CollaborationManager;
  let metrics: MetricsCollector;
  let awareness: AwarenessService;
  let presenceHandler: PresenceHandler;
  let documentStore: DocumentStore;
  let access: FakeAccessChecker;

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
    access = new FakeAccessChecker();

    manager = new CollaborationManager({
      io,
      documentStore,
      documentAccess: access,
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
      access.allow('doc-join-test', 'user-join-1');

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
      access.allow('doc-sync-test', 'user-sync-1');

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
      access.allow('doc-notify-test', 'user-notify-1');
      access.allow('doc-notify-test', 'user-notify-2');

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
      access.allow('doc-update-test', 'user-update-1');
      access.allow('doc-update-test', 'user-update-2');

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
      access.allow('doc-cursor-test', 'user-cursor-1');
      access.allow('doc-cursor-test', 'user-cursor-2');

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
      access.allow('doc-disc-test', 'user-disc-1');
      access.allow('doc-disc-test', 'user-disc-2');

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
      access.allow('doc-leave-test', 'user-leave-1');
      access.allow('doc-leave-test', 'user-leave-2');

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
    const DOC = 'doc-private';
    const OWNER = 'user-owner';
    const INTRUDER = 'user-intruder';
    const VIEWER = 'user-viewer';

    it('passes the caller identity, token and share token to the access checker', async () => {
      const client = await connectClient(OWNER, 'Owner');
      access.allow(DOC, OWNER);
      await joinDocument(client, DOC, 'share-abc');
      const last = access.requests[access.requests.length - 1];
      expect(last.documentId).toBe(DOC);
      expect(last.user.userId).toBe(OWNER);
      expect(last.shareToken).toBe('share-abc');
      // nosemgrep: javascript.jsonwebtoken.security.jwt-hardcode.hardcoded-jwt-secret
      expect(jwt.verify(last.token, JWT_SECRET)).toMatchObject({ sub: OWNER });
      client.disconnect();
    });

    it('refuses join-document for a user without a grant and sends no state', async () => {
      const owner = await connectClient(OWNER, 'Owner');
      const intruder = await connectClient(INTRUDER, 'Intruder');
      access.allow(DOC, OWNER);
      const intruderEvents: string[] = [];
      intruder.onAny((event) => intruderEvents.push(event));

      expect(await joinDocument(owner, DOC)).toEqual({ success: true });
      expect(await joinDocument(intruder, DOC)).toEqual({
        success: false,
        error: 'Access denied',
      });
      await waitFor(100);

      expect(intruderEvents).not.toContain('sync-document');
      expect(intruderEvents).not.toContain('presence-update');
      expect(awareness.getDocumentUsers(DOC).map((u) => u.userId)).toEqual([OWNER]);
      owner.disconnect();
      intruder.disconnect();
    });

    it('ignores updates, history and comments for a document the socket never joined', async () => {
      const owner = await connectClient(OWNER, 'Owner');
      const intruder = await connectClient(INTRUDER, 'Intruder');
      access.allow(DOC, OWNER);
      const ownerEvents: string[] = [];
      const intruderEvents: Array<{ event: string; data: unknown }> = [];
      owner.onAny((event) => ownerEvents.push(event));
      intruder.onAny((event, data) => intruderEvents.push({ event, data }));

      expect(await joinDocument(owner, DOC)).toEqual({ success: true });
      await joinDocument(intruder, DOC);

      intruder.emit('document-update', { documentId: DOC, update: validUpdate('pwned') });
      intruder.emit('request-history', { documentId: DOC });
      intruder.emit('request-snapshot', { documentId: DOC });
      intruder.emit('comment-add', {
        documentId: DOC,
        comment: { id: 'c1', threadId: 't1', content: 'hi', rangeStart: 0, rangeEnd: 1 },
      });
      intruder.emit('cursor-update', {
        documentId: DOC,
        cursor: { index: 1, length: 0 },
        selection: null,
      });
      await waitFor(200);

      expect(ownerEvents).not.toContain('document-update');
      expect(ownerEvents).not.toContain('comment-added');
      expect(ownerEvents).not.toContain('cursor-update');
      expect(ownerEvents).not.toContain('snapshot-created');
      const received = intruderEvents.map((e) => e.event);
      expect(received).not.toContain('document-history');
      expect(received).not.toContain('snapshot-created');
      expect(received).toContain('access-denied');
      expect(received).toContain('history-error');
      expect(manager.getDocument(DOC)!.getText('content').toString()).toBe('');
      owner.disconnect();
      intruder.disconnect();
    });

    it('lets a view-only grant read but not write', async () => {
      const owner = await connectClient(OWNER, 'Owner');
      const viewer = await connectClient(VIEWER, 'Viewer');
      access.allow(DOC, OWNER, 'edit');
      access.allow(DOC, VIEWER, 'view');
      const ownerEvents: string[] = [];
      const viewerEvents: Array<{ event: string; data: unknown }> = [];
      owner.onAny((event) => ownerEvents.push(event));
      viewer.onAny((event, data) => viewerEvents.push({ event, data }));

      expect(await joinDocument(owner, DOC)).toEqual({ success: true });
      expect(await joinDocument(viewer, DOC, 'share-token')).toEqual({ success: true });
      await waitFor(50);
      expect(viewerEvents.map((e) => e.event)).toContain('sync-document');

      owner.emit('document-update', {
        documentId: DOC,
        update: validUpdate('owner text'),
      });
      viewer.emit('document-update', {
        documentId: DOC,
        update: validUpdate('viewer text'),
      });
      viewer.emit('request-history', { documentId: DOC });
      viewer.emit('request-snapshot', { documentId: DOC });
      await waitFor(200);

      const viewerReceived = viewerEvents.map((e) => e.event);
      expect(viewerReceived).toContain('document-update');
      expect(viewerReceived).toContain('document-history');
      expect(viewerReceived).toContain('document-update-error');
      expect(viewerReceived).toContain('snapshot-error');
      expect(ownerEvents).not.toContain('document-update');
      expect(manager.getDocument(DOC)!.getText('content').toString()).toBe('owner text');
      owner.disconnect();
      viewer.disconnect();
    });

    it('does not let a granted socket act on a different document id', async () => {
      const owner = await connectClient(OWNER, 'Owner');
      const other = await connectClient(INTRUDER, 'Intruder');
      access.allow(DOC, OWNER);
      access.allow('doc-intruder-own', INTRUDER);
      const ownerEvents: string[] = [];
      owner.onAny((event) => ownerEvents.push(event));

      expect(await joinDocument(owner, DOC)).toEqual({ success: true });
      expect(await joinDocument(other, 'doc-intruder-own')).toEqual({ success: true });
      other.emit('document-update', { documentId: DOC, update: validUpdate('cross') });
      other.emit('cursor-update', {
        documentId: DOC,
        cursor: { index: 1, length: 0 },
        selection: null,
      });
      await waitFor(150);

      expect(ownerEvents).not.toContain('document-update');
      expect(ownerEvents).not.toContain('cursor-update');
      owner.disconnect();
      other.disconnect();
    });

    it('fails closed when the access check itself fails', async () => {
      const owner = await connectClient(OWNER, 'Owner');
      access.allow(DOC, OWNER);
      access.failNext = true;
      expect(await joinDocument(owner, DOC)).toEqual({
        success: false,
        error: 'Failed to join document',
      });
      expect(awareness.getDocumentUserCount(DOC)).toBe(0);
      owner.disconnect();
    });

    it('rejects a join without a documentId', async () => {
      const owner = await connectClient(OWNER, 'Owner');
      const res = await new Promise<{ success: boolean }>((resolve) => {
        owner.emit('join-document', {}, (r: { success: boolean }) => resolve(r));
      });
      expect(res.success).toBe(false);
      owner.disconnect();
    });

    afterEach(() => {
      access.grants.clear();
      access.requests = [];
    });
  });
});
