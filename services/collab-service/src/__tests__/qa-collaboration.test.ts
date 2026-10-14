/**
 * QA collaboration unit tests: CRDT merging, comment/typing fanout, snapshots,
 * document switching, reconnect and persistence lifecycle of CollaborationManager.
 */
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

const JWT_SECRET = 'qa-collab-unit-secret';

function createToken(payload: Record<string, unknown>): string {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: '1h' }); // nosemgrep: javascript.jsonwebtoken.security.jwt-hardcode.hardcoded-jwt-secret
}

const redisStore = new Map<string, Buffer>();
const listStore = new Map<string, string[]>();

const mockRedis = {
  get: jest.fn(async (k: string) => redisStore.get(k) ?? null),
  set: jest.fn(async (k: string, v: Buffer) => {
    redisStore.set(k, v);
  }),
  del: jest.fn().mockResolvedValue(undefined),
  hset: jest.fn().mockResolvedValue(undefined),
  hget: jest.fn().mockResolvedValue(null),
  hgetall: jest.fn().mockResolvedValue({}),
  hdel: jest.fn().mockResolvedValue(undefined),
  hincrby: jest.fn().mockResolvedValue(1),
  lpush: jest.fn(async (k: string, v: string) => {
    listStore.set(k, [v, ...(listStore.get(k) ?? [])]);
  }),
  lrange: jest.fn(async (k: string, s: number, e: number) =>
    (listStore.get(k) ?? []).slice(s, e + 1),
  ),
  ltrim: jest.fn().mockResolvedValue(undefined),
  llen: jest.fn(async (k: string) => (listStore.get(k) ?? []).length),
  expire: jest.fn().mockResolvedValue(undefined),
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

function waitFor<T>(client: ClientSocket, event: string, timeoutMs = 3000): Promise<T> {
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

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function encodeTextInsert(base: Y.Doc, index: number, text: string): string {
  const before = Y.encodeStateVector(base);
  base.getText('content').insert(index, text);
  return Buffer.from(Y.encodeStateAsUpdate(base, before)).toString('base64');
}

describe('QA: CollaborationManager collaboration flows', () => {
  let io: SocketIOServer;
  let httpServer: ReturnType<typeof createServer>;
  let manager: CollaborationManager;
  let awareness: AwarenessService;
  let port = 0;
  const clients: ClientSocket[] = [];

  beforeAll((done) => {
    httpServer = createServer();
    io = new SocketIOServer(httpServer, { cors: { origin: '*' } });
    io.use(createAuthMiddleware(JWT_SECRET, mockLogger));
    awareness = new AwarenessService(mockLogger);
    const presenceHandler = new PresenceHandler(awareness, mockLogger);
    const documentStore = new DocumentStore(mockRedis, mockLogger);
    manager = new CollaborationManager({
      io,
      documentStore,
      awareness,
      presenceHandler,
      metrics: new MetricsCollector(),
      logger: mockLogger,
      persistIntervalMs: 600000,
      snapshotIntervalMs: 600000,
    });
    manager.start();
    httpServer.listen(0, () => {
      const addr = httpServer.address();
      port = typeof addr === 'object' && addr ? addr.port : 0;
      done();
    });
  }, 15000);

  afterEach(() => {
    while (clients.length) {
      const c = clients.pop();
      if (c?.connected) c.disconnect();
    }
  });

  afterAll((done) => {
    manager.stop();
    io.close();
    httpServer.close(() => done());
  });

  function connect(userId: string, name: string): Promise<ClientSocket> {
    return new Promise((resolve, reject) => {
      const client = clientIO(`http://localhost:${port}`, {
        auth: { token: createToken({ sub: userId, name, email: `${userId}@qa.test` }) },
        transports: ['websocket'],
        reconnection: false,
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

  it('merges concurrent Yjs edits from two users without conflict', async () => {
    const docId = 'qa-crdt-merge';
    const a = await connect('qa-a', 'Alice');
    const b = await connect('qa-b', 'Bob');
    await join(a, docId);
    await join(b, docId);

    const docA = new Y.Doc();
    const docB = new Y.Doc();
    const updA = encodeTextInsert(docA, 0, 'Hello ');
    const updB = encodeTextInsert(docB, 0, 'World');

    const bGets = waitFor<{ update: string }>(b, 'document-update');
    const aGets = waitFor<{ update: string }>(a, 'document-update');
    a.emit('document-update', { documentId: docId, update: updA });
    b.emit('document-update', { documentId: docId, update: updB });
    const [fromA, fromB] = await Promise.all([bGets, aGets]);

    Y.applyUpdate(docB, Buffer.from(fromA.update, 'base64'));
    Y.applyUpdate(docA, Buffer.from(fromB.update, 'base64'));
    await sleep(50);

    const serverText = manager.getDocument(docId)!.getText('content').toString();
    expect(docA.getText('content').toString()).toBe(docB.getText('content').toString());
    expect(serverText).toBe(docA.getText('content').toString());
    expect(serverText).toContain('Hello ');
    expect(serverText).toContain('World');
  });

  it('sends merged server state to a late joiner via sync-document', async () => {
    const docId = 'qa-late-join';
    const a = await connect('qa-a2', 'Alice');
    await join(a, docId);
    const local = new Y.Doc();
    a.emit('document-update', {
      documentId: docId,
      update: encodeTextInsert(local, 0, 'persisted text'),
    });
    await sleep(100);

    const late = await connect('qa-late', 'Late');
    const syncP = waitFor<{ documentId: string; state: string }>(late, 'sync-document');
    await join(late, docId);
    const sync = await syncP;
    const replica = new Y.Doc();
    Y.applyUpdate(replica, Buffer.from(sync.state, 'base64'));
    expect(sync.documentId).toBe(docId);
    expect(replica.getText('content').toString()).toBe('persisted text');
  });

  it('emits document-update-error and does not broadcast a corrupt Yjs update', async () => {
    const docId = 'qa-corrupt';
    const a = await connect('qa-c1', 'A');
    const b = await connect('qa-c2', 'B');
    await join(a, docId);
    await join(b, docId);
    const received: unknown[] = [];
    b.on('document-update', (d) => received.push(d));
    const errP = waitFor<{ error: string }>(a, 'document-update-error');
    a.emit('document-update', {
      documentId: docId,
      update: Buffer.from([0xff, 0xff, 0xff, 0x01, 0x02]).toString('base64'),
    });
    const err = await errP;
    await sleep(100);
    expect(err.error).toMatch(/Failed to apply update/);
    expect(received).toHaveLength(0);
  });

  it('ignores updates for a document the server has not loaded', async () => {
    const a = await connect('qa-u1', 'A');
    const b = await connect('qa-u2', 'B');
    await join(b, 'qa-unknown-room');
    const received: unknown[] = [];
    b.on('document-update', (d) => received.push(d));
    a.emit('document-update', { documentId: 'qa-never-joined', update: { text: 'x' } });
    await sleep(150);
    expect(received).toHaveLength(0);
    expect(manager.getDocument('qa-never-joined')).toBeUndefined();
  });

  it('relays legacy JSON updates to other members of the room only', async () => {
    const docId = 'qa-legacy-json';
    const a = await connect('qa-l1', 'A');
    const b = await connect('qa-l2', 'B');
    const outsider = await connect('qa-l3', 'C');
    await join(a, docId);
    await join(b, docId);
    await join(outsider, 'qa-other-room');
    const outsiderGot: unknown[] = [];
    const selfGot: unknown[] = [];
    outsider.on('document-update', (d) => outsiderGot.push(d));
    a.on('document-update', (d) => selfGot.push(d));
    const bGets = waitFor<{ update: { text: string } }>(b, 'document-update');
    a.emit('document-update', { documentId: docId, update: { text: 'hi' } });
    expect((await bGets).update).toEqual({ text: 'hi' });
    await sleep(100);
    expect(outsiderGot).toHaveLength(0);
    expect(selfGot).toHaveLength(0);
  });

  it('broadcasts presence-update with both users and distinct colors', async () => {
    const docId = 'qa-presence';
    const a = await connect('qa-p1', 'Alice');
    await join(a, docId);
    const b = await connect('qa-p2', 'Bob');
    const presP = waitFor<{
      count: number;
      users: Array<{ userId: string; color: string; displayName: string }>;
    }>(a, 'presence-update');
    const joinedP = waitFor<{ userId: string; displayName: string }>(a, 'user-joined');
    await join(b, docId);
    const [presence, joined] = await Promise.all([presP, joinedP]);
    expect(joined).toMatchObject({ userId: 'qa-p2', displayName: 'Bob' });
    expect(presence.count).toBe(2);
    const colors = new Set(presence.users.map((u) => u.color));
    expect(colors.size).toBe(2);
    expect(presence.users.map((u) => u.displayName).sort()).toEqual(['Alice', 'Bob']);
  });

  it('relays cursor-update with sender identity and color', async () => {
    const docId = 'qa-cursor';
    const a = await connect('qa-cur1', 'Alice');
    const b = await connect('qa-cur2', 'Bob');
    await join(a, docId);
    await join(b, docId);
    const p = waitFor<{
      userId: string;
      displayName: string;
      color: string;
      cursor: { index: number };
    }>(b, 'cursor-update');
    a.emit('cursor-update', {
      documentId: docId,
      cursor: { index: 4, length: 0 },
      selection: null,
    });
    const evt = await p;
    expect(evt).toMatchObject({
      userId: 'qa-cur1',
      displayName: 'Alice',
      cursor: { index: 4 },
    });
    expect(evt.color).toMatch(/^#[0-9A-F]{6}$/i);
  });

  it('relays typing-indicator to peers', async () => {
    const docId = 'qa-typing';
    const a = await connect('qa-t1', 'Alice');
    const b = await connect('qa-t2', 'Bob');
    await join(a, docId);
    await join(b, docId);
    const p = waitFor<{ userId: string; isTyping: boolean }>(b, 'typing-indicator');
    a.emit('typing-indicator', { documentId: docId, isTyping: true });
    expect(await p).toMatchObject({ userId: 'qa-t1', isTyping: true });
  });

  it('broadcasts comment-added to sender and peers with server-side author', async () => {
    const docId = 'qa-comment';
    const a = await connect('qa-cm1', 'Alice');
    const b = await connect('qa-cm2', 'Bob');
    await join(a, docId);
    await join(b, docId);
    const aP = waitFor<Record<string, unknown>>(a, 'comment-added');
    const bP = waitFor<Record<string, unknown>>(b, 'comment-added');
    a.emit('comment-add', {
      documentId: docId,
      comment: {
        id: 'c1',
        threadId: 't1',
        content: 'Looks good',
        rangeStart: 0,
        rangeEnd: 4,
        author: { userId: 'spoofed', displayName: 'Mallory' },
      },
    });
    const [atA, atB] = await Promise.all([aP, bP]);
    expect(atA).toEqual(atB);
    expect(atB).toMatchObject({ id: 'c1', content: 'Looks good', documentId: docId });
    expect(atB.author).toEqual({ userId: 'qa-cm1', displayName: 'Alice' });
    expect(typeof atB.createdAt).toBe('string');
  });

  it('broadcasts comment-updated and comment-deleted to peers', async () => {
    const docId = 'qa-comment-mut';
    const a = await connect('qa-cu1', 'Alice');
    const b = await connect('qa-cu2', 'Bob');
    await join(a, docId);
    await join(b, docId);
    const upP = waitFor<Record<string, unknown>>(b, 'comment-updated');
    a.emit('comment-update', { documentId: docId, commentId: 'c1', content: 'edited' });
    expect(await upP).toMatchObject({
      commentId: 'c1',
      content: 'edited',
      updatedBy: { userId: 'qa-cu1' },
    });
    const delP = waitFor<Record<string, unknown>>(b, 'comment-deleted');
    a.emit('comment-delete', { documentId: docId, commentId: 'c1' });
    expect(await delP).toEqual({ commentId: 'c1', deletedBy: 'qa-cu1' });
  });

  it('returns snapshot-error for snapshots of an unloaded document', async () => {
    const a = await connect('qa-s0', 'A');
    const p = waitFor<{ error: string }>(a, 'snapshot-error');
    a.emit('request-snapshot', { documentId: 'qa-no-such-doc' });
    expect((await p).error).toBe('Document not found');
  });

  it('creates a labelled snapshot visible to peers and in history', async () => {
    const docId = 'qa-snapshot';
    const a = await connect('qa-s1', 'Alice');
    const b = await connect('qa-s2', 'Bob');
    await join(a, docId);
    await join(b, docId);
    a.emit('document-update', {
      documentId: docId,
      update: encodeTextInsert(new Y.Doc(), 0, 'v1'),
    });
    await sleep(50);
    const aP = waitFor<{ id: string; label: string; createdBy: string }>(
      a,
      'snapshot-created',
    );
    const bP = waitFor<{ id: string }>(b, 'snapshot-created');
    a.emit('request-snapshot', { documentId: docId, label: 'milestone' });
    const [snapA, snapB] = await Promise.all([aP, bP]);
    expect(snapA.id).toBe(snapB.id);
    expect(snapA).toMatchObject({ label: 'milestone', createdBy: 'qa-s1' });

    const histP = waitFor<{ snapshots: Array<{ id: string; state: string }> }>(
      a,
      'document-history',
    );
    a.emit('request-history', { documentId: docId, limit: 5 });
    const hist = await histP;
    expect(hist.snapshots[0].id).toBe(snapA.id);
    const restored = new Y.Doc();
    Y.applyUpdate(restored, Buffer.from(hist.snapshots[0].state, 'base64'));
    expect(restored.getText('content').toString()).toBe('v1');
  });

  it('switching documents removes the user from the old room presence', async () => {
    const a = await connect('qa-sw1', 'Alice');
    const b = await connect('qa-sw2', 'Bob');
    await join(a, 'qa-room-1');
    await join(b, 'qa-room-1');
    const leftP = waitFor<{ userId: string }>(a, 'user-left');
    await join(b, 'qa-room-2');
    expect((await leftP).userId).toBe('qa-sw2');
    expect(awareness.getDocumentUsers('qa-room-1').map((u) => u.userId)).toEqual([
      'qa-sw1',
    ]);
    expect(awareness.getDocumentUsers('qa-room-2').map((u) => u.userId)).toEqual([
      'qa-sw2',
    ]);
  });

  it('persists and evicts the Y.Doc when the last user leaves, then restores on rejoin', async () => {
    const docId = 'qa-evict';
    const a = await connect('qa-e1', 'Alice');
    await join(a, docId);
    a.emit('document-update', {
      documentId: docId,
      update: encodeTextInsert(new Y.Doc(), 0, 'durable'),
    });
    await sleep(50);
    a.emit('leave-document', { documentId: docId });
    await sleep(150);
    expect(manager.getDocument(docId)).toBeUndefined();
    expect(redisStore.has(`doc:state:${docId}`)).toBe(true);

    const syncP = waitFor<{ state: string }>(a, 'sync-document');
    await join(a, docId);
    const replica = new Y.Doc();
    Y.applyUpdate(replica, Buffer.from((await syncP).state, 'base64'));
    expect(replica.getText('content').toString()).toBe('durable');
  });

  it('reconnect after a dropped socket rejoins and resyncs edits made while offline', async () => {
    const docId = 'qa-reconnect';
    const a = await connect('qa-r1', 'Alice');
    const b = await connect('qa-r2', 'Bob');
    await join(a, docId);
    await join(b, docId);
    const leftP = waitFor<{ userId: string }>(a, 'user-left');
    b.disconnect();
    expect((await leftP).userId).toBe('qa-r2');
    expect(awareness.getDocumentUserCount(docId)).toBe(1);

    a.emit('document-update', {
      documentId: docId,
      update: encodeTextInsert(new Y.Doc(), 0, 'while-offline'),
    });
    await sleep(50);

    const b2 = await connect('qa-r2', 'Bob');
    const syncP = waitFor<{ state: string }>(b2, 'sync-document');
    await join(b2, docId);
    const replica = new Y.Doc();
    Y.applyUpdate(replica, Buffer.from((await syncP).state, 'base64'));
    expect(replica.getText('content').toString()).toBe('while-offline');
    expect(awareness.getDocumentUserCount(docId)).toBe(2);
  });

  it('handles concurrent joins of a new document with a single Y.Doc instance', async () => {
    const docId = 'qa-concurrent-join';
    const sockets = await Promise.all(
      [1, 2, 3, 4].map((i) => connect(`qa-cj${i}`, `U${i}`)),
    );
    await Promise.all(sockets.map((s) => join(s, docId)));
    expect(manager.getDocument(docId)).toBeDefined();
    expect(awareness.getDocumentUserCount(docId)).toBe(4);
  });
});
