import WebSocket from 'ws';

export function protectWebSocket(
  socket: WebSocket,
  expiresAt: number,
  authorize: () => Promise<boolean>,
): void {
  let incoming = Promise.resolve();
  let outgoing = Promise.resolve();
  const send = socket.send.bind(socket);
  const emit = socket.emit.bind(socket);
  const stop = () => socket.terminate();
  const allowed = async () =>
    socket.readyState === WebSocket.OPEN &&
    Date.now() < expiresAt &&
    (await authorize()) &&
    Date.now() < expiresAt &&
    socket.readyState === WebSocket.OPEN;

  socket.send = ((...args: Parameters<WebSocket['send']>) => {
    outgoing = outgoing
      .then(async () => {
        if (await allowed()) send(...args);
        else stop();
      })
      .catch(stop);
  }) as WebSocket['send'];

  socket.emit = ((...args: Parameters<WebSocket['emit']>) => {
    if (args[0] !== 'message') return emit(...args);
    incoming = incoming
      .then(async () => {
        if (await allowed()) emit(...args);
        else stop();
      })
      .catch(stop);
    return true;
  }) as WebSocket['emit'];

  const timer = setTimeout(
    stop,
    Math.min(Math.max(0, expiresAt - Date.now()), 2147483647),
  );
  timer.unref();
  socket.once('close', () => clearTimeout(timer));
}
