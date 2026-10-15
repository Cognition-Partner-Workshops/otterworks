import jwt from 'jsonwebtoken';
import { randomBytes } from 'crypto';
import type { Socket } from 'socket.io';
import type { Server as SocketIOServer } from 'socket.io';
import {
  createAuthMiddleware,
  extractUserFromSocket,
  type AuthenticatedSocket,
} from '../middleware/auth';
import { AwarenessService } from '../services/awareness';
import { PresenceHandler } from '../handlers/presence';

const SECRET = randomBytes(32).toString('hex');

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

function fakeSocket(handshake: {
  auth?: Record<string, unknown>;
  headers?: Record<string, string>;
}): Socket {
  return {
    id: 'sock-1',
    handshake: { auth: {}, headers: {}, ...handshake },
  } as unknown as Socket;
}

function runAuth(socket: Socket): Error | undefined {
  let result: Error | undefined;
  createAuthMiddleware(SECRET, mockLogger)(socket, (err) => {
    result = err as Error | undefined;
  });
  return result;
}

describe('createAuthMiddleware', () => {
  it('accepts a bearer token from the Authorization header', () => {
    const token = jwt.sign({ sub: 'u-1', name: 'Una' }, SECRET);
    const socket = fakeSocket({ headers: { authorization: `Bearer ${token}` } });
    expect(runAuth(socket)).toBeUndefined();
    expect((socket as AuthenticatedSocket).user?.userId).toBe('u-1');
  });

  it('falls back to display_name and then Anonymous', () => {
    const withSnake = fakeSocket({
      auth: { token: jwt.sign({ sub: 'u-2', display_name: 'Snake' }, SECRET) },
    });
    runAuth(withSnake);
    expect((withSnake as AuthenticatedSocket).user?.displayName).toBe('Snake');

    const bare = fakeSocket({ auth: { token: jwt.sign({ sub: 'u-3' }, SECRET) } });
    runAuth(bare);
    expect((bare as AuthenticatedSocket).user).toMatchObject({
      displayName: 'Anonymous',
      email: '',
      roles: [],
    });
  });

  it('rejects an expired token', () => {
    const token = jwt.sign(
      { sub: 'u-4', exp: Math.floor(Date.now() / 1000) - 60 },
      SECRET,
    );
    expect(runAuth(fakeSocket({ auth: { token } }))?.message).toBe(
      'Invalid or expired token',
    );
  });

  it('rejects a token signed with another secret', () => {
    const token = jwt.sign({ sub: 'u-5' }, 'some-other-secret');
    expect(runAuth(fakeSocket({ auth: { token } }))?.message).toBe(
      'Invalid or expired token',
    );
  });

  it('extractUserFromSocket returns an anonymous identity for unauthenticated sockets', () => {
    expect(extractUserFromSocket(fakeSocket({})).userId).toBe('anon-sock-1');
  });
});

describe('PresenceHandler', () => {
  let awareness: AwarenessService;
  let handler: PresenceHandler;

  beforeEach(() => {
    jest.useRealTimers();
    awareness = new AwarenessService(mockLogger);
    handler = new PresenceHandler(awareness, mockLogger);
  });

  it('reports presence and active documents with user counts', () => {
    awareness.addUser('doc-a', 's1', 'u1', 'A', 'a@t.io');
    awareness.addUser('doc-a', 's2', 'u2', 'B', 'b@t.io');
    awareness.addUser('doc-b', 's3', 'u3', 'C', 'c@t.io');

    expect(handler.getDocumentPresence('doc-a')).toMatchObject({
      documentId: 'doc-a',
      count: 2,
    });
    expect(handler.getDocumentPresence('nope')).toEqual({
      documentId: 'nope',
      users: [],
      count: 0,
    });
    expect(handler.getActiveDocuments()).toEqual(
      expect.arrayContaining([
        { documentId: 'doc-a', userCount: 2 },
        { documentId: 'doc-b', userCount: 1 },
      ]),
    );
  });

  it('broadcastPresenceUpdate emits to the document room', () => {
    awareness.addUser('doc-a', 's1', 'u1', 'A', 'a@t.io');
    const emit = jest.fn();
    const io = { to: jest.fn(() => ({ emit })) } as unknown as SocketIOServer;
    handler.broadcastPresenceUpdate(io, 'doc-a');
    expect(io.to).toHaveBeenCalledWith('doc:doc-a');
    expect(emit).toHaveBeenCalledWith(
      'presence-update',
      expect.objectContaining({ count: 1 }),
    );
  });

  it('evicts idle users, tells their socket the session expired and reports empty documents', () => {
    jest.useFakeTimers();
    awareness.addUser('doc-idle', 's-idle', 'u-idle', 'Idle', 'i@t.io');
    const evicted = {
      emit: jest.fn(),
      leave: jest.fn(),
      to: jest.fn(() => ({ emit: jest.fn() })),
    };
    const roomEmit = jest.fn();
    const io = {
      sockets: { sockets: new Map([['s-idle', evicted]]) },
      to: jest.fn(() => ({ emit: roomEmit })),
    } as unknown as SocketIOServer;
    const onEmpty = jest.fn();

    const timer = handler.startCleanupInterval(io, 1000, 5000, onEmpty);
    jest.advanceTimersByTime(7000);
    clearInterval(timer);

    expect(evicted.emit).toHaveBeenCalledWith('session-expired', {
      documentId: 'doc-idle',
      reason: 'idle_timeout',
    });
    expect(evicted.leave).toHaveBeenCalledWith('doc:doc-idle');
    expect(onEmpty).toHaveBeenCalledWith('doc-idle');
    expect(awareness.getDocumentUserCount('doc-idle')).toBe(0);
    jest.useRealTimers();
  });

  it('does not evict users whose activity was refreshed', () => {
    jest.useFakeTimers();
    awareness.addUser('doc-live', 's-live', 'u-live', 'Live', 'l@t.io');
    const io = {
      sockets: { sockets: new Map() },
      to: jest.fn(() => ({ emit: jest.fn() })),
    } as unknown as SocketIOServer;
    const timer = handler.startCleanupInterval(io, 1000, 5000);
    for (let i = 0; i < 8; i++) {
      jest.advanceTimersByTime(1000);
      awareness.refreshActivity('s-live');
    }
    clearInterval(timer);
    expect(awareness.getDocumentUserCount('doc-live')).toBe(1);
    jest.useRealTimers();
  });
});
