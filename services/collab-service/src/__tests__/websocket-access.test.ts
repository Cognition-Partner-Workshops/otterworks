import { once } from 'events';
import WebSocket, { WebSocketServer } from 'ws';
import { protectWebSocket } from '../services/websocket-access';

describe('Yjs transport access lifetime', () => {
  let server: WebSocketServer;
  let client: WebSocket;
  let connection: WebSocket;
  let authorized: boolean;
  let expiresAt: number;

  beforeEach(async () => {
    authorized = true;
    expiresAt = Date.now() + 60000;
    server = new WebSocketServer({ port: 0 });
    server.on('connection', (socket) => {
      connection = socket;
      protectWebSocket(socket, expiresAt, async () => authorized);
    });
    await once(server, 'listening');
    const address = server.address();
    if (!address || typeof address === 'string') throw new Error('Expected TCP address');
    client = new WebSocket(`ws://127.0.0.1:${address.port}`);
    await once(client, 'open');
  });

  afterEach(async () => {
    client.terminate();
    for (const socket of server.clients) socket.terminate();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  it('allows authorized traffic in both directions', async () => {
    const incoming = once(connection, 'message');
    client.send('edit');
    expect((await incoming)[0].toString()).toBe('edit');
    const outgoing = once(client, 'message');
    connection.send('document');
    expect((await outgoing)[0].toString()).toBe('document');
  });

  it('evicts a revoked subscriber before sending document data', async () => {
    const received = jest.fn();
    client.on('message', received);
    authorized = false;
    const closed = once(client, 'close');
    connection.send('sensitive document');
    await closed;
    expect(received).not.toHaveBeenCalled();
  });

  it('evicts a revoked editor before processing its update', async () => {
    const edit = jest.fn();
    connection.on('message', edit);
    authorized = false;
    const closed = once(client, 'close');
    client.send('unauthorized edit');
    await closed;
    expect(edit).not.toHaveBeenCalled();
  });

  it('disconnects an idle subscriber when its JWT expires', async () => {
    protectWebSocket(connection, Date.now() + 50, async () => true);
    await once(client, 'close');
    expect(client.readyState).toBe(WebSocket.CLOSED);
  });
});
