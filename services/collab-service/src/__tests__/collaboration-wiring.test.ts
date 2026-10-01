import type { Server as SocketIOServer, Socket } from 'socket.io';
import { CollaborationManager } from '../handlers/collaboration';
import { DocumentStore } from '../services/document-store';
import { AwarenessService } from '../services/awareness';
import { PresenceHandler } from '../handlers/presence';
import { MetricsCollector } from '../metrics';

const mockLogger = {
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  debug: jest.fn(),
} as never;

describe('CollaborationManager socket wiring', () => {
  it('registers exactly the client-facing socket events', async () => {
    let onConnection: ((socket: Socket) => void) | undefined;
    const io = {
      on: jest.fn((event: string, handler: (socket: Socket) => void) => {
        if (event === 'connection') onConnection = handler;
      }),
    } as unknown as SocketIOServer;
    const socketOn = jest.fn();
    const socket = { id: 'sock-1', on: socketOn } as unknown as Socket;
    const awareness = new AwarenessService(mockLogger);
    const manager = new CollaborationManager({
      io,
      documentStore: {} as DocumentStore,
      awareness,
      presenceHandler: new PresenceHandler(awareness, mockLogger),
      metrics: new MetricsCollector(),
      logger: mockLogger,
      persistIntervalMs: 600000,
      snapshotIntervalMs: 600000,
    });

    manager.start();
    onConnection?.(socket);
    await manager.stop();

    expect(socketOn.mock.calls.map(([event]) => event)).toEqual([
      'join-document',
      'leave-document',
      'document-update',
      'cursor-update',
      'typing-indicator',
      'comment-add',
      'comment-update',
      'comment-delete',
      'request-snapshot',
      'request-history',
      'disconnect',
    ]);
  });
});
