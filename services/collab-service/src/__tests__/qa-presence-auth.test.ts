/** QA unit tests for presence bookkeeping, stale-user eviction and socket auth. */
import jwt from 'jsonwebtoken';
import type { Socket } from 'socket.io';
import { AwarenessService } from '../services/awareness';
import { PresenceHandler } from '../handlers/presence';
import {
  createAuthMiddleware,
  extractUserFromSocket,
  AuthenticatedSocket,
} from '../middleware/auth';
import { DocumentStore } from '../services/document-store';
import { RedisAdapter } from '../services/redis-adapter';

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

const SECRET = 'qa-auth-secret';

function fakeSocket(handshake: Record<string, unknown>, id = 'sock-1'): Socket {
  return { id, handshake } as unknown as Socket;
}

describe('QA: AwarenessService presence edge cases', () => {
  let awareness: AwarenessService;
  beforeEach(() => {
    awareness = new AwarenessService(mockLogger);
  });

  it('cycles through the 20-colour palette and wraps around', () => {
    const colors = Array.from(
      { length: 21 },
      (_, i) => awareness.addUser('doc', `s${i}`, `u${i}`, `U${i}`, '').color,
    );
    expect(new Set(colors.slice(0, 20)).size).toBe(20);
    expect(colors[20]).toBe(colors[0]);
  });

  it('moves a socket between documents and drops the empty old state', () => {
    awareness.addUser('doc-a', 's1', 'u1', 'A', '');
    awareness.addUser('doc-b', 's1', 'u1', 'A', '');
    expect(awareness.getDocumentUserCount('doc-a')).toBe(0);
    expect(awareness.getActiveDocumentIds()).toEqual(['doc-b']);
    expect(awareness.getUserDocument('s1')).toBe('doc-b');
  });

  it('tracks the same user in two tabs as two presence entries', () => {
    awareness.addUser('doc', 'tab-1', 'u1', 'A', '');
    awareness.addUser('doc', 'tab-2', 'u1', 'A', '');
    expect(awareness.getDocumentUserCount('doc')).toBe(2);
    awareness.removeUser('tab-1');
    expect(awareness.getDocumentUsers('doc').map((u) => u.userId)).toEqual(['u1']);
  });

  it('refreshActivity keeps an active editor from being evicted', () => {
    jest.useFakeTimers();
    try {
      jest.setSystemTime(1_000_000);
      awareness.addUser('doc', 'idle', 'u1', 'A', '');
      awareness.addUser('doc', 'busy', 'u2', 'B', '');
      jest.setSystemTime(1_000_000 + 9_000);
      expect(awareness.refreshActivity('busy')).toBe(true);
      jest.setSystemTime(1_000_000 + 12_000);
      const removed = awareness.cleanupStaleUsers(10_000);
      expect(removed.map((r) => r.socketId)).toEqual(['idle']);
      expect(awareness.getDocumentUsers('doc').map((u) => u.userId)).toEqual(['u2']);
    } finally {
      jest.useRealTimers();
    }
  });

  it('refreshActivity/updateCursor/setTyping are no-ops for unknown sockets', () => {
    expect(awareness.refreshActivity('ghost')).toBe(false);
    expect(awareness.updateCursor('ghost', { index: 1, length: 0 }, null)).toBeNull();
    expect(awareness.setTyping('ghost', true)).toBeNull();
  });

  it('cleanupStaleUsers removes document state once everyone is stale', () => {
    jest.useFakeTimers();
    try {
      jest.setSystemTime(0);
      awareness.addUser('doc', 's1', 'u1', 'A', '');
      jest.setSystemTime(100_000);
      awareness.cleanupStaleUsers(1_000);
      expect(awareness.getActiveDocumentIds()).toEqual([]);
      expect(awareness.getUserDocument('s1')).toBeNull();
    } finally {
      jest.useRealTimers();
    }
  });

  it('stores selection alongside cursor', () => {
    awareness.addUser('doc', 's1', 'u1', 'A', '');
    const res = awareness.updateCursor(
      's1',
      { index: 2, length: 0 },
      { index: 2, length: 5 },
    );
    expect(res?.selection).toEqual({ index: 2, length: 5 });
  });
});

describe('QA: PresenceHandler', () => {
  it('summarises presence and active documents', () => {
    const awareness = new AwarenessService(mockLogger);
    const handler = new PresenceHandler(awareness, mockLogger);
    awareness.addUser('d1', 's1', 'u1', 'A', '');
    awareness.addUser('d1', 's2', 'u2', 'B', '');
    awareness.addUser('d2', 's3', 'u3', 'C', '');
    expect(handler.getDocumentPresence('d1').count).toBe(2);
    expect(handler.getDocumentPresence('missing')).toEqual({
      documentId: 'missing',
      users: [],
      count: 0,
    });
    expect(handler.getActiveDocuments()).toEqual(
      expect.arrayContaining([
        { documentId: 'd1', userCount: 2 },
        { documentId: 'd2', userCount: 1 },
      ]),
    );
  });

  it('cleanup interval notifies evicted sockets, peers and triggers empty-doc eviction', () => {
    jest.useFakeTimers();
    try {
      jest.setSystemTime(0);
      const awareness = new AwarenessService(mockLogger);
      const handler = new PresenceHandler(awareness, mockLogger);
      awareness.addUser('doc', 'sock-x', 'u1', 'A', '');

      const roomEmit = jest.fn();
      const evicted = {
        emit: jest.fn(),
        leave: jest.fn(),
        to: jest.fn(() => ({ emit: roomEmit })),
      };
      const ioEmit = jest.fn();
      const io = {
        sockets: { sockets: new Map([['sock-x', evicted]]) },
        to: jest.fn(() => ({ emit: ioEmit })),
      };
      const onEmpty = jest.fn();
      const timer = handler.startCleanupInterval(io as never, 1000, 500, onEmpty);
      jest.advanceTimersByTime(1000);
      clearInterval(timer);

      expect(evicted.emit).toHaveBeenCalledWith('session-expired', {
        documentId: 'doc',
        reason: 'idle_timeout',
      });
      expect(evicted.leave).toHaveBeenCalledWith('doc:doc');
      expect(roomEmit).toHaveBeenCalledWith('user-left', {
        socketId: 'sock-x',
        userId: 'u1',
      });
      expect(ioEmit).toHaveBeenCalledWith('presence-update', {
        documentId: 'doc',
        users: [],
        count: 0,
      });
      expect(onEmpty).toHaveBeenCalledWith('doc');
    } finally {
      jest.useRealTimers();
    }
  });
});

describe('QA: socket auth middleware', () => {
  const mw = createAuthMiddleware(SECRET, mockLogger);

  function run(socket: Socket): Error | undefined {
    let result: Error | undefined;
    let called = false;
    mw(socket, (err?: Error) => {
      called = true;
      result = err;
    });
    expect(called).toBe(true);
    return result;
  }

  it('accepts a Bearer authorization header', () => {
    const token = jwt.sign(
      { sub: 'u1', email: 'a@x', name: 'Alice', roles: ['USER'] },
      SECRET,
    );
    const s = fakeSocket({ auth: {}, headers: { authorization: `Bearer ${token}` } });
    expect(run(s)).toBeUndefined();
    expect((s as AuthenticatedSocket).user).toEqual({
      userId: 'u1',
      email: 'a@x',
      displayName: 'Alice',
      roles: ['USER'],
    });
  });

  it('falls back to display_name then Anonymous for the display name', () => {
    const s1 = fakeSocket({
      auth: { token: jwt.sign({ sub: 'u1', display_name: 'Disp' }, SECRET) },
    });
    run(s1);
    expect((s1 as AuthenticatedSocket).user?.displayName).toBe('Disp');
    const s2 = fakeSocket({ auth: { token: jwt.sign({ sub: 'u2' }, SECRET) } });
    run(s2);
    expect((s2 as AuthenticatedSocket).user?.displayName).toBe('Anonymous');
  });

  it('rejects expired tokens', () => {
    const token = jwt.sign(
      { sub: 'u1', exp: Math.floor(Date.now() / 1000) - 60 },
      SECRET,
    );
    expect(run(fakeSocket({ auth: { token } }))?.message).toBe(
      'Invalid or expired token',
    );
  });

  it('rejects tokens signed with a different secret', () => {
    const token = jwt.sign({ sub: 'u1' }, 'other-secret');
    expect(run(fakeSocket({ auth: { token } }))?.message).toBe(
      'Invalid or expired token',
    );
  });

  it('rejects when no token is supplied anywhere', () => {
    expect(run(fakeSocket({ auth: {}, headers: {} }))?.message).toBe(
      'Authentication required',
    );
  });

  it('extractUserFromSocket returns an anonymous identity for unauthenticated sockets', () => {
    expect(extractUserFromSocket(fakeSocket({}, 'abc'))).toEqual({
      userId: 'anon-abc',
      email: '',
      displayName: 'Anonymous',
      roles: [],
    });
  });
});

describe('QA: DocumentStore snapshot round-trip', () => {
  it('trims snapshots to maxSnapshots and restores a snapshot by id', async () => {
    const list: string[] = [];
    const redis = {
      lpush: jest.fn(async (_k: string, v: string) => {
        list.unshift(v);
      }),
      llen: jest.fn(async () => list.length),
      ltrim: jest.fn(async (_k: string, s: number, e: number) => {
        list.splice(e + 1);
        list.splice(0, s);
      }),
      lrange: jest.fn(async (_k: string, s: number, e: number) => list.slice(s, e + 1)),
      expire: jest.fn(),
    } as unknown as RedisAdapter;
    const store = new DocumentStore(redis, mockLogger, { maxSnapshots: 2 });
    const s1 = await store.createSnapshot('d', Buffer.from('one'), 'u');
    await store.createSnapshot('d', Buffer.from('two'), 'u');
    const s3 = await store.createSnapshot('d', Buffer.from('three'), 'u');
    expect(redis.ltrim).toHaveBeenCalledWith('doc:snapshots:d', 0, 1);
    expect(list).toHaveLength(2);
    expect(await store.getSnapshotState('d', s1.id)).toBeNull();
    const state = await store.getSnapshotState('d', s3.id);
    expect(Buffer.from(state!).toString()).toBe('three');
  });
});
