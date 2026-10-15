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

const JWT_SECRET = 'test-secret-key-for-realtime-tests';

function createToken(payload: Record<string, unknown>): string {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: '1h' }); // nosemgrep: javascript.jsonwebtoken.security.jwt-hardcode.hardcoded-jwt-secret
}

function createInMemoryRedis() {
  const kv = new Map<string, Buffer>();
  const hashes = new Map<string, Record<string, string>>();
  const lists = new Map<string, string[]>();
  return {
    kv,
    get: jest.fn(async (key: string) => kv.get(key) ?? null),
    set: jest.fn(async (key: string, value: Buffer) => {
      kv.set(key, Buffer.from(value));
    }),
    del: jest.fn(async (key: string) => {
      kv.delete(key);
      hashes.delete(key);
      lists.delete(key);
    }),
    hset: jest.fn(async (key: string, field: string, value: string) => {
      hashes.set(key, { ...(hashes.get(key) ?? {}), [field]: value });
    }),
    hget: jest.fn(async (key: string, field: string) => hashes.get(key)?.[field] ?? null),
    hgetall: jest.fn(async (key: string) => hashes.get(key) ?? {}),
    hincrby: jest.fn(async (key: string, field: string, by: number) => {
      const next = parseInt(hashes.get(key)?.[field] ?? '0', 10) + by;
      hashes.set(key, { ...(hashes.get(key) ?? {}), [field]: String(next) });
      return next;
    }),
    lpush: jest.fn(async (key: string, value: string) => {
      lists.set(key, [value, ...(lists.get(key) ?? [])]);
    }),
    lrange: jest.fn(async (key: string, start: number, stop: number) =>
      (lists.get(key) ?? []).slice(start, stop + 1),
    ),
    ltrim: jest.fn(async (key: string, start: number, stop: number) => {
      lists.set(key, (lists.get(key) ?? []).slice(start, stop + 1));
    }),
    llen: jest.fn(async (key: string) => (lists.get(key) ?? []).length),
    expire: jest.fn(async () => undefined),
    ping: jest.fn(async () => true),
  };
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

function encodeTextUpdate(text: string, base?: Y.Doc): { doc: Y.Doc; update: string } {
  const doc = base ?? new Y.Doc();
  const before = Y.encodeStateVector(doc);
  doc.getText('content').insert(doc.getText('content').length, text);
  const update = Y.encodeStateAsUpdate(doc, before);
  return { doc, update: Buffer.from(update).toString('base64') };
}

function textFromState(base64State: string): string {
  const doc = new Y.Doc();
  Y.applyUpdate(doc, new Uint8Array(Buffer.from(base64State, 'base64')));
  return doc.getText('content').toString();
}

describe('CollaborationManager realtime flows', () => {
  let io: SocketIOServer;
  let httpServer: ReturnType<typeof createServer>;
  let manager: CollaborationManager;
  let awareness: AwarenessService;
  let redis: ReturnType<typeof createInMemoryRedis>;
  let port: number;
  const openClients: ClientSocket[] = [];

  beforeAll((done) => {
    httpServer = createServer();
    io = new SocketIOServer(httpServer, { cors: { origin: '*' } });
    io.use(createAuthMiddleware(JWT_SECRET, mockLogger));

    redis = createInMemoryRedis();
    awareness = new AwarenessService(mockLogger);
    const presenceHandler = new PresenceHandler(awareness, mockLogger);
    const documentStore = new DocumentStore(redis as unknown as RedisAdapter, mockLogger);

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

  afterAll(async () => {
    await manager.stop();
    io.close();
    await new Promise((resolve) => httpServer.close(resolve));
  });

  afterEach(() => {
    while (openClients.length) openClients.pop()?.disconnect();
  });

  function connect(userId: string, displayName: string): Promise<ClientSocket> {
    return new Promise((resolve, reject) => {
      const client = clientIO(`http://localhost:${port}`, {
        auth: {
          token: createToken({ sub: userId, name: displayName, email: `${userId}@t.io` }),
        },
        transports: ['websocket'],
        reconnection: false,
      });
      openClients.push(client);
      client.on('connect', () => resolve(client));
      client.on('connect_error', reject);
      setTimeout(() => reject(new Error('Connection timeout')), 5000);
    });
  }

  function join(client: ClientSocket, documentId: string): Promise<{ success: boolean }> {
    return new Promise((resolve) =>
      client.emit('join-document', { documentId }, resolve),
    );
  }

  function next<T = unknown>(
    client: ClientSocket,
    event: string,
    timeoutMs = 3000,
  ): Promise<T> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error(`Timed out waiting for ${event}`)),
        timeoutMs,
      );
      client.once(event, (data: T) => {
        clearTimeout(timer);
        resolve(data);
      });
    });
  }

  function expectSilence(client: ClientSocket, event: string, ms = 300): Promise<void> {
    return new Promise((resolve, reject) => {
      const handler = () => reject(new Error(`Unexpected ${event}`));
      client.once(event, handler);
      setTimeout(() => {
        client.off(event, handler);
        resolve();
      }, ms);
    });
  }

  async function pair(documentId: string): Promise<[ClientSocket, ClientSocket]> {
    const alice = await connect('alice', 'Alice');
    const bob = await connect('bob', 'Bob');
    await join(alice, documentId);
    await join(bob, documentId);
    return [alice, bob];
  }

  describe('Yjs document updates', () => {
    it('applies a base64 Yjs update to the server doc and relays it verbatim', async () => {
      const [alice, bob] = await pair('rt-apply');
      const { update } = encodeTextUpdate('hello');
      const relayed = next<{ documentId: string; update: string }>(
        bob,
        'document-update',
      );
      alice.emit('document-update', { documentId: 'rt-apply', update });

      expect(await relayed).toEqual({ documentId: 'rt-apply', update });
      expect(manager.getDocument('rt-apply')?.getText('content').toString()).toBe(
        'hello',
      );
    });

    it('does not echo an update back to its sender', async () => {
      const [alice] = await pair('rt-no-echo');
      const silence = expectSilence(alice, 'document-update');
      alice.emit('document-update', {
        documentId: 'rt-no-echo',
        update: encodeTextUpdate('x').update,
      });
      await silence;
    });

    it('persists merged state to the document store after each update', async () => {
      const [alice] = await pair('rt-persist');
      alice.emit('document-update', {
        documentId: 'rt-persist',
        update: encodeTextUpdate('saved').update,
      });
      await new Promise((r) => setTimeout(r, 200));

      const stored = redis.kv.get('doc:state:rt-persist');
      expect(stored).toBeDefined();
      expect(textFromState(stored!.toString('base64'))).toBe('saved');
    });

    it('converges when two users edit concurrently', async () => {
      const [alice, bob] = await pair('rt-concurrent');
      const aliceDoc = new Y.Doc();
      const bobDoc = new Y.Doc();
      aliceDoc.clientID = 1;
      bobDoc.clientID = 2;
      const a = encodeTextUpdate('A', aliceDoc).update;
      const b = encodeTextUpdate('B', bobDoc).update;

      const bobGetsA = next(bob, 'document-update');
      const aliceGetsB = next(alice, 'document-update');
      alice.emit('document-update', { documentId: 'rt-concurrent', update: a });
      bob.emit('document-update', { documentId: 'rt-concurrent', update: b });
      await Promise.all([bobGetsA, aliceGetsB]);

      Y.applyUpdate(aliceDoc, new Uint8Array(Buffer.from(b, 'base64')));
      Y.applyUpdate(bobDoc, new Uint8Array(Buffer.from(a, 'base64')));
      const serverText = manager
        .getDocument('rt-concurrent')
        ?.getText('content')
        .toString();
      expect(aliceDoc.getText('content').toString()).toBe(
        bobDoc.getText('content').toString(),
      );
      expect(serverText).toBe(aliceDoc.getText('content').toString());
      expect(serverText).toHaveLength(2);
    });

    it('emits document-update-error and does not relay a corrupt update', async () => {
      const [alice, bob] = await pair('rt-corrupt');
      const silence = expectSilence(bob, 'document-update');
      const error = next<{ error: string }>(alice, 'document-update-error');
      alice.emit('document-update', {
        documentId: 'rt-corrupt',
        update: Buffer.from([0xff, 0xff, 0xff, 0x01]).toString('base64'),
      });
      expect((await error).error).toBe('Failed to apply update');
      await silence;
    });

    it('ignores updates for a document the server has not loaded', async () => {
      const alice = await connect('alice', 'Alice');
      alice.emit('document-update', {
        documentId: 'rt-never-joined',
        update: encodeTextUpdate('x').update,
      });
      await new Promise((r) => setTimeout(r, 200));
      expect(manager.getDocument('rt-never-joined')).toBeUndefined();
    });

    it('sends the accumulated state to a user who joins later', async () => {
      const [alice] = await pair('rt-late-join');
      alice.emit('document-update', {
        documentId: 'rt-late-join',
        update: encodeTextUpdate('early').update,
      });
      await new Promise((r) => setTimeout(r, 150));

      const carol = await connect('carol', 'Carol');
      const sync = next<{ state: string }>(carol, 'sync-document');
      await join(carol, 'rt-late-join');
      expect(textFromState((await sync).state)).toBe('early');
    });
  });

  describe('Reconnect', () => {
    it('restores persisted state after every client disconnected and reconnects', async () => {
      const alice = await connect('alice', 'Alice');
      await join(alice, 'rt-reconnect');
      alice.emit('document-update', {
        documentId: 'rt-reconnect',
        update: encodeTextUpdate('durable').update,
      });
      await new Promise((r) => setTimeout(r, 150));
      alice.disconnect();
      await new Promise((r) => setTimeout(r, 300));
      expect(manager.getDocument('rt-reconnect')).toBeUndefined();

      const again = await connect('alice', 'Alice');
      const sync = next<{ state: string }>(again, 'sync-document');
      await join(again, 'rt-reconnect');
      expect(textFromState((await sync).state)).toBe('durable');
    });

    it('a rejoining socket replaces its old presence entry instead of duplicating it', async () => {
      const alice = await connect('alice', 'Alice');
      await join(alice, 'rt-rejoin');
      await join(alice, 'rt-rejoin');
      expect(awareness.getDocumentUserCount('rt-rejoin')).toBe(1);
    });
  });

  describe('Presence', () => {
    it('broadcasts presence-update with both users to the room', async () => {
      const alice = await connect('alice', 'Alice');
      await join(alice, 'rt-presence');
      const bob = await connect('bob', 'Bob');
      const presence = next<{ count: number; users: Array<{ displayName: string }> }>(
        alice,
        'presence-update',
      );
      await join(bob, 'rt-presence');
      const update = await presence;
      expect(update.count).toBe(2);
      expect(update.users.map((u) => u.displayName).sort()).toEqual(['Alice', 'Bob']);
    });

    it('assigns distinct cursor colours to concurrent users', async () => {
      await pair('rt-colors');
      const colors = awareness.getDocumentUsers('rt-colors').map((u) => u.color);
      expect(new Set(colors).size).toBe(2);
    });

    it('relays typing indicators with the typing user identity', async () => {
      const [alice, bob] = await pair('rt-typing');
      const typing = next<{ userId: string; displayName: string; isTyping: boolean }>(
        bob,
        'typing-indicator',
      );
      alice.emit('typing-indicator', { documentId: 'rt-typing', isTyping: true });
      expect(await typing).toMatchObject({
        userId: 'alice',
        displayName: 'Alice',
        isTyping: true,
      });
      expect(
        awareness.getDocumentUsers('rt-typing').find((u) => u.userId === 'alice')
          ?.isTyping,
      ).toBe(true);
    });

    it('relays selection ranges along with the cursor', async () => {
      const [alice, bob] = await pair('rt-selection');
      const cursor = next<{ selection: { index: number; length: number } }>(
        bob,
        'cursor-update',
      );
      alice.emit('cursor-update', {
        documentId: 'rt-selection',
        cursor: { index: 4, length: 0 },
        selection: { index: 1, length: 3 },
      });
      expect((await cursor).selection).toEqual({ index: 1, length: 3 });
    });

    it('drops cursor updates from a socket that never joined', async () => {
      const [, bob] = await pair('rt-cursor-unjoined');
      const stranger = await connect('mallory', 'Mallory');
      const silence = expectSilence(bob, 'cursor-update');
      stranger.emit('cursor-update', {
        documentId: 'rt-cursor-unjoined',
        cursor: { index: 0, length: 0 },
        selection: null,
      });
      await silence;
    });

    it('moves a user out of the old room when switching documents', async () => {
      const [alice, bob] = await pair('rt-switch-a');
      const left = next<{ userId: string }>(bob, 'user-left');
      await join(alice, 'rt-switch-b');
      expect((await left).userId).toBe('alice');
      expect(awareness.getDocumentUsers('rt-switch-a').map((u) => u.userId)).toEqual([
        'bob',
      ]);
      expect(awareness.getDocumentUsers('rt-switch-b').map((u) => u.userId)).toEqual([
        'alice',
      ]);
    });
  });

  describe('Comments', () => {
    const comment = {
      id: 'c-1',
      threadId: 't-1',
      content: 'Looks good',
      rangeStart: 0,
      rangeEnd: 5,
    };

    it('delivers comment-added to the room and echoes it to the author', async () => {
      const [alice, bob] = await pair('rt-comment-add');
      const toBob = next<Record<string, unknown>>(bob, 'comment-added');
      const toAlice = next<Record<string, unknown>>(alice, 'comment-added');
      alice.emit('comment-add', { documentId: 'rt-comment-add', comment });
      const [b, a] = await Promise.all([toBob, toAlice]);
      expect(b).toMatchObject({
        ...comment,
        documentId: 'rt-comment-add',
        author: { userId: 'alice', displayName: 'Alice' },
      });
      expect(a).toEqual(b);
      expect(typeof b.createdAt).toBe('string');
    });

    it('stamps the author from the JWT, ignoring a client-supplied author', async () => {
      const [alice, bob] = await pair('rt-comment-spoof');
      const toAlice = next<{ author: { userId: string } }>(alice, 'comment-added');
      bob.emit('comment-add', {
        documentId: 'rt-comment-spoof',
        comment: { ...comment, author: { userId: 'alice', displayName: 'Alice' } },
      });
      expect((await toAlice).author.userId).toBe('bob');
    });

    it('relays comment-updated with the editor identity', async () => {
      const [alice, bob] = await pair('rt-comment-update');
      const updated = next<Record<string, unknown>>(bob, 'comment-updated');
      alice.emit('comment-update', {
        documentId: 'rt-comment-update',
        commentId: 'c-1',
        content: 'edited',
      });
      expect(await updated).toMatchObject({
        commentId: 'c-1',
        content: 'edited',
        updatedBy: { userId: 'alice' },
      });
    });

    it('relays comment-deleted with the deleting user', async () => {
      const [alice, bob] = await pair('rt-comment-delete');
      const deleted = next<Record<string, unknown>>(bob, 'comment-deleted');
      alice.emit('comment-delete', { documentId: 'rt-comment-delete', commentId: 'c-1' });
      expect(await deleted).toEqual({ commentId: 'c-1', deletedBy: 'alice' });
    });

    // [REAL] comment-update/comment-delete have no ownership check: any room member can
    // rewrite or delete another user's comment. Left failing on purpose (see PR).
    it('rejects edits to a comment by someone other than its author', async () => {
      const [alice, bob] = await pair('rt-comment-owner');
      alice.emit('comment-add', { documentId: 'rt-comment-owner', comment });
      await next(bob, 'comment-added');
      const silence = expectSilence(alice, 'comment-updated', 400);
      bob.emit('comment-update', {
        documentId: 'rt-comment-owner',
        commentId: 'c-1',
        content: 'hijacked',
      });
      await silence;
    });
  });

  describe('Snapshots and history', () => {
    it('creates a labelled snapshot visible to the whole room', async () => {
      const [alice, bob] = await pair('rt-snapshot');
      alice.emit('document-update', {
        documentId: 'rt-snapshot',
        update: encodeTextUpdate('v1').update,
      });
      await new Promise((r) => setTimeout(r, 100));
      const mine = next<{ label: string; createdBy: string; state: string }>(
        alice,
        'snapshot-created',
      );
      const theirs = next<{ id: string }>(bob, 'snapshot-created');
      alice.emit('request-snapshot', { documentId: 'rt-snapshot', label: 'milestone' });
      const [snap, other] = await Promise.all([mine, theirs]);
      expect(snap).toMatchObject({ label: 'milestone', createdBy: 'alice' });
      expect(textFromState(snap.state)).toBe('v1');
      expect(other.id).toBe((snap as unknown as { id: string }).id);
    });

    it('returns snapshot-error for a document not loaded in memory', async () => {
      const alice = await connect('alice', 'Alice');
      const err = next<{ error: string }>(alice, 'snapshot-error');
      alice.emit('request-snapshot', { documentId: 'rt-snapshot-missing' });
      expect((await err).error).toBe('Document not found');
    });

    it('returns history newest-first and honours the limit', async () => {
      const [alice] = await pair('rt-history');
      for (const label of ['one', 'two', 'three']) {
        const created = next(alice, 'snapshot-created');
        alice.emit('request-snapshot', { documentId: 'rt-history', label });
        await created;
      }
      const history = next<{ snapshots: Array<{ label: string }> }>(
        alice,
        'document-history',
      );
      alice.emit('request-history', { documentId: 'rt-history', limit: 2 });
      expect((await history).snapshots.map((s) => s.label)).toEqual(['three', 'two']);
    });
  });

  describe('Lifecycle', () => {
    it('loads a document once under concurrent joins', async () => {
      const clients = await Promise.all([
        connect('u1', 'U1'),
        connect('u2', 'U2'),
        connect('u3', 'U3'),
      ]);
      await Promise.all(clients.map((c) => join(c, 'rt-concurrent-join')));
      expect(manager.getDocument('rt-concurrent-join')).toBeDefined();
      expect(awareness.getDocumentUserCount('rt-concurrent-join')).toBe(3);
      expect(
        redis.get.mock.calls.filter(([k]) => k === 'doc:state:rt-concurrent-join'),
      ).toHaveLength(1);
    });

    it('keeps the document in memory if persistence fails during cleanup', async () => {
      const alice = await connect('alice', 'Alice');
      await join(alice, 'rt-persist-fail');
      redis.set.mockRejectedValueOnce(new Error('redis down'));
      alice.emit('leave-document', { documentId: 'rt-persist-fail' });
      await new Promise((r) => setTimeout(r, 200));
      expect(manager.getDocument('rt-persist-fail')).toBeDefined();
    });
  });
});
