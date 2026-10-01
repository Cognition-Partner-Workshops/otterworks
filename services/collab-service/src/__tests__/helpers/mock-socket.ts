import type { Socket } from 'socket.io';
import type { AuthenticatedUser } from '../../middleware/auth';

export interface MockSocket {
  socket: Socket;
  emit: jest.Mock;
  to: jest.Mock;
  roomEmit: jest.Mock;
}

export function createMockSocket(user?: AuthenticatedUser, id = 'socket-1'): MockSocket {
  const roomEmit = jest.fn();
  const emit = jest.fn();
  const to = jest.fn().mockReturnValue({ emit: roomEmit });
  const socket = { id, user, emit, to } as unknown as Socket;
  return { socket, emit, to, roomEmit };
}

export const testUser: AuthenticatedUser = {
  userId: 'user-1',
  email: 'alice@test.com',
  displayName: 'Alice',
  roles: ['user'],
};
