import { randomBytes } from 'crypto';
import { createServer } from 'http';
import { Server as SocketIOServer } from 'socket.io';
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

const jwtSecret = randomBytes(32).toString('hex');

const redisStore = new Map<string, string>();
const redisLists = new Map<string, string[]>();
const mockRedis = {
  get: jest.fn(async (key: string) => redisStore.get(key) ?? null),
  set: jest.fn(async (key: string, value: string) => {
    redisStore.set(key, value);
  }),
  del: jest.fn().mockResolvedValue(undefined),
  hset: jest.fn().mockResolvedValue(undefined),
  hget: jest.fn().mockResolvedValue(null),
  hgetall: jest.fn().mockResolvedValue({}),
  hdel: jest.fn().mockResolvedValue(undefined),
  hincrby: jest.fn().mockResolvedValue(1),
  lpush: jest.fn(async (key: string, value: string) => {
    redisLists.set(key, [value, ...(redisLists.get(key) ?? [])]);
  }),
  lrange: jest.fn(async (key: string, start: number, stop: number) =>
    (redisLists.get(key) ?? []).slice(start, stop + 1),
  ),
  ltrim: jest.fn().mockResolvedValue(undefined),
  llen: jest.fn(async (key: string) => (redisLists.get(key) ?? []).length),
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

function yjsUpdate(text: string, clientId: number): string {
  const doc = new Y.Doc();
  doc.clientID = clientId;
  doc.getText('qa').insert(0, text);
  return Buffer.from(Y.encodeStateAsUpdate(doc)).toString('base64');
}

function textOf(stateB64: string): string {
  const doc = new Y.Doc();
  Y.applyUpdate(doc, new Uint8Array(Buffer.from(stateB64, 'base64')));
  return doc.getText('qa').toString();
}

function nextEvent<T = any>(
  client: ClientSocket,
  event: string,
  timeoutMs = 3000,
): Promise<T> {
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

function noEvent(client: ClientSocket, event: string, waitMs = 400): Promise<boolean> {
  return new Promise((resolve) => {
    const handler = () => resolve(false);
    client.once(event, handler);
    setTimeout(() => {
      client.off(event, handler);
      resolve(true);
    }, waitMs);
  });
}

describe('Collaboration QA: comments, history, presence, reconnect', () => {
  let io: SocketIOServer;
  let httpServer: ReturnType<typeof createServer>;
  let manager: CollaborationManager;
  let awareness: AwarenessService;
  let port = 0;
  const clients: ClientSocket[] = [];

  beforeAll((done) => {
    httpServer = createServer();
    io = new SocketIOServer(httpServer, { cors: { origin: '*' } });
    io.use(createAuthMiddleware(jwtSecret, mockLogger));
    awareness = new AwarenessService(mockLogger);
    manager = new CollaborationManager({
      io,
      documentStore: new DocumentStore(mockRedis, mockLogger),
      awareness,
      presenceHandler: new PresenceHandler(awareness, mockLogger),
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
  });

  afterEach(() => {
    while (clients.length) clients.pop()?.disconnect();
  });

  afterAll((done) => {
    manager.stop();
    io.close();
    httpServer.close(() => done());
  });

  function connect(
    userId: string,
    claims: Record<string, unknown> = {},
  ): Promise<ClientSocket> {
    const token = jwt.sign(
      { sub: userId, name: `User ${userId}`, email: `${userId}@qa.test`, ...claims },
      jwtSecret,
      {
        expiresIn: '5m',
      },
    );
    return new Promise((resolve, reject) => {
      const client = clientIO(`http://localhost:${port}`, {
        auth: { token },
        transports: ['websocket'],
        reconnection: false,
      });
      clients.push(client);
      client.on('connect', () => resolve(client));
      client.on('connect_error', reject);
    });
  }

  async function join(
    client: ClientSocket,
    documentId: string,
  ): Promise<{ state: string }> {
    const sync = nextEvent<{ state: string }>(client, 'sync-document');
    const ack = await new Promise((resolve) =>
      client.emit('join-document', { documentId }, resolve),
    );
    expect(ack).toEqual({ success: true });
    return sync;
  }

  it('relays Yjs updates and syncs the merged state to a late joiner', async () => {
    const a = await connect('alice');
    const b = await connect('bob');
    await join(a, 'doc-merge');
    await join(b, 'doc-merge');

    const relayed = nextEvent(b, 'document-update');
    a.emit('document-update', { documentId: 'doc-merge', update: yjsUpdate('A', 1) });
    expect((await relayed).update).toBe(yjsUpdate('A', 1));

    const toA = nextEvent(a, 'document-update');
    b.emit('document-update', { documentId: 'doc-merge', update: yjsUpdate('B', 2) });
    await toA;

    const late = await connect('carol');
    const { state } = await join(late, 'doc-merge');
    expect(textOf(state).split('').sort().join('')).toBe('AB');
  });

  it('rejects a corrupt CRDT update without broadcasting it', async () => {
    const a = await connect('alice');
    const b = await connect('bob');
    await join(a, 'doc-corrupt');
    await join(b, 'doc-corrupt');
    const err = nextEvent(a, 'document-update-error');
    const silent = noEvent(b, 'document-update');
    a.emit('document-update', {
      documentId: 'doc-corrupt',
      update: Buffer.from([255, 255, 255, 255]).toString('base64'),
    });
    expect((await err).error).toBe('Failed to apply update');
    expect(await silent).toBe(true);
  });

  it('ignores updates for a document no one has joined', async () => {
    const a = await connect('alice');
    a.emit('document-update', {
      documentId: 'doc-never-joined',
      update: yjsUpdate('x', 3),
    });
    await new Promise((r) => setTimeout(r, 200));
    expect(manager.getDocument('doc-never-joined')).toBeUndefined();
  });

  it('stamps comment authors server-side and echoes comment-added to sender and room', async () => {
    const a = await connect('alice');
    const b = await connect('bob');
    await join(a, 'doc-comments');
    await join(b, 'doc-comments');

    const toA = nextEvent(a, 'comment-added');
    const toB = nextEvent(b, 'comment-added');
    a.emit('comment-add', {
      documentId: 'doc-comments',
      comment: {
        id: 'c1',
        threadId: 't1',
        content: 'hi',
        rangeStart: 0,
        rangeEnd: 2,
        author: { userId: 'mallory', displayName: 'Mallory' },
      },
    });
    const [atA, atB] = await Promise.all([toA, toB]);
    expect(atA).toEqual(atB);
    expect(atB.author).toEqual({ userId: 'alice', displayName: 'User alice' });
    expect(atB.documentId).toBe('doc-comments');
    expect(Date.parse(atB.createdAt)).not.toBeNaN();
  });

  it('broadcasts comment-updated and comment-deleted to the other room members only', async () => {
    const a = await connect('alice');
    const b = await connect('bob');
    await join(a, 'doc-comment-edit');
    await join(b, 'doc-comment-edit');

    const updated = nextEvent(b, 'comment-updated');
    const notEchoed = noEvent(a, 'comment-updated');
    a.emit('comment-update', {
      documentId: 'doc-comment-edit',
      commentId: 'c1',
      content: 'edited',
    });
    expect(await updated).toMatchObject({
      commentId: 'c1',
      content: 'edited',
      updatedBy: { userId: 'alice' },
    });
    expect(await notEchoed).toBe(true);

    const deleted = nextEvent(b, 'comment-deleted');
    a.emit('comment-delete', { documentId: 'doc-comment-edit', commentId: 'c1' });
    expect(await deleted).toEqual({ commentId: 'c1', deletedBy: 'alice' });
  });

  it('fans out typing indicators', async () => {
    const a = await connect('alice');
    const b = await connect('bob');
    await join(a, 'doc-typing');
    await join(b, 'doc-typing');
    const typing = nextEvent(b, 'typing-indicator');
    a.emit('typing-indicator', { documentId: 'doc-typing', isTyping: true });
    expect(await typing).toMatchObject({
      userId: 'alice',
      displayName: 'User alice',
      isTyping: true,
    });
  });

  it('creates a labelled snapshot visible to the room and in request-history', async () => {
    const a = await connect('alice');
    const b = await connect('bob');
    await join(a, 'doc-history');
    await join(b, 'doc-history');

    const toA = nextEvent(a, 'snapshot-created');
    const toB = nextEvent(b, 'snapshot-created');
    a.emit('request-snapshot', { documentId: 'doc-history', label: 'v1' });
    const [snapA, snapB] = await Promise.all([toA, toB]);
    expect(snapA.id).toBe(snapB.id);
    expect(snapA).toMatchObject({
      documentId: 'doc-history',
      label: 'v1',
      createdBy: 'alice',
    });

    const history = nextEvent(b, 'document-history');
    b.emit('request-history', { documentId: 'doc-history' });
    const { snapshots } = await history;
    expect(snapshots.map((s: { id: string }) => s.id)).toContain(snapA.id);
  });

  it('returns snapshot-error for a document that is not loaded', async () => {
    const a = await connect('alice');
    const err = nextEvent(a, 'snapshot-error');
    a.emit('request-snapshot', { documentId: 'doc-not-loaded' });
    expect(await err).toEqual({
      documentId: 'doc-not-loaded',
      error: 'Document not found',
    });
  });

  it('moves a socket out of its old room when it joins another document', async () => {
    const watcher = await connect('alice');
    const mover = await connect('bob');
    await join(watcher, 'doc-room-1');
    await join(mover, 'doc-room-1');
    const left = nextEvent(watcher, 'user-left');
    await join(mover, 'doc-room-2');
    expect((await left).userId).toBe('bob');
    expect(awareness.getDocumentUserCount('doc-room-1')).toBe(1);
    expect(awareness.getDocumentUserCount('doc-room-2')).toBe(1);
  });

  it('restores persisted state after every client disconnects and one reconnects', async () => {
    const a = await connect('alice');
    await join(a, 'doc-reconnect');
    a.emit('document-update', {
      documentId: 'doc-reconnect',
      update: yjsUpdate('persisted', 4),
    });
    await new Promise((r) => setTimeout(r, 200));
    a.disconnect();
    await new Promise((r) => setTimeout(r, 300));
    expect(manager.getDocument('doc-reconnect')).toBeUndefined();

    const again = await connect('alice');
    const { state } = await join(again, 'doc-reconnect');
    expect(textOf(state)).toBe('persisted');
  });

  // [REAL] defects: these tests describe the secure behaviour and are expected to fail on main.
  it.failing('[REAL] rejects refresh tokens on the Socket.IO handshake', async () => {
    await expect(connect('alice', { type: 'refresh' })).rejects.toThrow();
  });

  it.failing(
    '[REAL] does not deliver comment-add from a socket that never joined the room',
    async () => {
      const member = await connect('alice');
      await join(member, 'doc-private');
      const outsider = await connect('mallory');
      const silent = noEvent(member, 'comment-added');
      outsider.emit('comment-add', {
        documentId: 'doc-private',
        comment: { id: 'x', threadId: 'x', content: 'spam', rangeStart: 0, rangeEnd: 0 },
      });
      expect(await silent).toBe(true);
    },
  );

  it.failing(
    '[REAL] does not relay cursor updates into a room the socket is not in',
    async () => {
      const member = await connect('alice');
      await join(member, 'doc-cursor-private');
      const outsider = await connect('mallory');
      await join(outsider, 'doc-elsewhere');
      const silent = noEvent(member, 'cursor-update');
      outsider.emit('cursor-update', {
        documentId: 'doc-cursor-private',
        cursor: { index: 0, length: 0 },
        selection: null,
      });
      expect(await silent).toBe(true);
    },
  );
});
