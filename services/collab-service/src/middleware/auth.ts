import jwt from 'jsonwebtoken';
import type { Socket } from 'socket.io';
import type { ExtendedError } from 'socket.io/dist/namespace';
import type { Logger } from 'pino';
import type { IncomingMessage } from 'http';
import type { RequestHandler } from 'express';

export interface AuthenticatedUser {
  userId: string;
  email: string;
  displayName: string;
  roles: string[];
}

export interface AuthenticatedSocket extends Socket {
  user?: AuthenticatedUser;
  /** The verified bearer token, kept so downstream authorization calls run as the caller. */
  token?: string;
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

export function verifyToken(token: string, jwtSecret: string): AuthenticatedUser {
  const decoded = jwt.verify(token, jwtSecret) as JwtPayload;
  return {
    userId: decoded.sub,
    email: decoded.email || '',
    displayName: decoded.name || decoded.display_name || 'Anonymous',
    roles: decoded.roles || [],
  };
}

export function extractBearerToken(req: IncomingMessage): string | undefined {
  const header = req.headers.authorization;
  if (header && header.startsWith('Bearer ')) {
    return header.slice('Bearer '.length).trim() || undefined;
  }
  return undefined;
}

export function createAuthMiddleware(jwtSecret: string, logger: Logger) {
  return (socket: Socket, next: (err?: ExtendedError) => void): void => {
    const token =
      socket.handshake.auth?.token ||
      socket.handshake.headers?.authorization?.replace('Bearer ', '');

    if (!token) {
      logger.warn({ socketId: socket.id }, 'connection_rejected: no token provided');
      next(new Error('Authentication required'));
      return;
    }

    try {
      const decoded = verifyToken(token, jwtSecret);

      const authSocket = socket as AuthenticatedSocket;
      authSocket.user = decoded;
      authSocket.token = token;

      logger.debug(
        { socketId: socket.id, userId: decoded.userId },
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

/** Express middleware: the HTTP endpoints require the same bearer token the sockets do. */
export function createHttpAuthMiddleware(
  jwtSecret: string,
  logger: Logger,
): RequestHandler {
  return (req, res, next) => {
    const token = extractBearerToken(req);
    if (!token) {
      res.status(401).json({ error: 'Authentication required' });
      return;
    }
    try {
      res.locals.user = verifyToken(token, jwtSecret);
      res.locals.token = token;
      next();
    } catch (err) {
      logger.warn(
        { error: (err as Error).message },
        'http_request_rejected: invalid token',
      );
      res.status(401).json({ error: 'Invalid or expired token' });
    }
  };
}

export function extractTokenFromSocket(socket: Socket): string {
  return (socket as AuthenticatedSocket).token || '';
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
