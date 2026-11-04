import jwt from 'jsonwebtoken';
import type { Socket } from 'socket.io';
import type { ExtendedError } from 'socket.io/dist/namespace';
import type { Logger } from 'pino';

export interface AuthenticatedUser {
  userId: string;
  email: string;
  displayName: string;
  roles: string[];
}

export interface AuthenticatedSocket extends Socket {
  user?: AuthenticatedUser;
  authToken?: string;
}

interface JwtPayload {
  sub: string;
  email?: string;
  name?: string;
  display_name?: string;
  roles?: string[];
  iat?: number;
  exp?: number;
}

export function extractBearerToken(header: string | undefined): string | undefined {
  if (!header || !header.startsWith('Bearer ')) return undefined;
  const token = header.slice('Bearer '.length).trim();
  return token || undefined;
}

/** Verifies a JWT and maps its claims to the collab user. Throws if invalid. */
export function verifyUserToken(token: string, jwtSecret: string): AuthenticatedUser {
  const decoded = jwt.verify(token, jwtSecret) as JwtPayload;
  if (!decoded || typeof decoded.sub !== 'string' || !decoded.sub) {
    throw new Error('Token has no subject');
  }
  return {
    userId: decoded.sub,
    email: decoded.email || '',
    displayName: decoded.name || decoded.display_name || 'Anonymous',
    roles: decoded.roles || [],
  };
}

export function createAuthMiddleware(jwtSecret: string, logger: Logger) {
  return (socket: Socket, next: (err?: ExtendedError) => void): void => {
    const token =
      socket.handshake.auth?.token ||
      extractBearerToken(socket.handshake.headers?.authorization);

    if (!token) {
      logger.warn({ socketId: socket.id }, 'connection_rejected: no token provided');
      next(new Error('Authentication required'));
      return;
    }

    try {
      const user = verifyUserToken(token, jwtSecret);
      const authSocket = socket as AuthenticatedSocket;
      authSocket.user = user;
      authSocket.authToken = token;

      logger.debug(
        { socketId: socket.id, userId: user.userId },
        'connection_authenticated',
      );
      next();
    } catch (err) {
      logger.warn(
        { socketId: socket.id, error: (err as Error).message },
        'connection_rejected: invalid token',
      );
      next(new Error('Invalid or expired token'));
    }
  };
}

export function extractUserFromSocket(socket: Socket): AuthenticatedUser {
  const authSocket = socket as AuthenticatedSocket;
  return (
    authSocket.user || {
      userId: `anon-${socket.id}`,
      email: '',
      displayName: 'Anonymous',
      roles: [],
    }
  );
}

export function extractTokenFromSocket(socket: Socket): string {
  return (socket as AuthenticatedSocket).authToken || '';
}
