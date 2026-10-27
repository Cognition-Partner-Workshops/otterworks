import jwt from 'jsonwebtoken';
import type { Request, RequestHandler } from 'express';
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
  /** Raw bearer token, replayed to document-service for permission checks. */
  token?: string;
}

export interface AuthenticatedRequest extends Request {
  user?: AuthenticatedUser;
}

export const ADMIN_ROLE = 'ADMIN';

interface JwtPayload {
  sub: string;
  email?: string;
  name?: string;
  display_name?: string;
  roles?: string[];
  iat?: number;
  exp?: number;
}

function toAuthenticatedUser(decoded: JwtPayload): AuthenticatedUser {
  return {
    userId: decoded.sub,
    email: decoded.email || '',
    displayName: decoded.name || decoded.display_name || 'Anonymous',
    roles: decoded.roles || [],
  };
}

export function verifyToken(token: string, jwtSecret: string): AuthenticatedUser {
  return toAuthenticatedUser(jwt.verify(token, jwtSecret) as JwtPayload);
}

export function isAdmin(user: AuthenticatedUser): boolean {
  return user.roles.some((role) => role.toUpperCase() === ADMIN_ROLE);
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
      const user = verifyToken(token, jwtSecret);
      const authSocket = socket as AuthenticatedSocket;
      authSocket.user = user;
      authSocket.token = token;

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

export function extractTokenFromSocket(socket: Socket): string | undefined {
  return (socket as AuthenticatedSocket).token;
}

/** Express middleware: require a valid bearer JWT and attach the user to the request. */
export function createHttpAuthMiddleware(
  jwtSecret: string,
  logger: Logger,
): RequestHandler {
  return (req, res, next) => {
    const header = req.headers.authorization;
    const token = header?.startsWith('Bearer ')
      ? header.slice('Bearer '.length)
      : undefined;
    if (!token) {
      res.status(401).json({ error: 'Authentication required' });
      return;
    }
    try {
      (req as AuthenticatedRequest).user = verifyToken(token, jwtSecret);
      next();
    } catch (err) {
      logger.warn(
        { path: req.path, error: (err as Error).message },
        'http_request_rejected',
      );
      res.status(401).json({ error: 'Invalid or expired token' });
    }
  };
}

/** Express middleware: require the authenticated user to hold the ADMIN role. */
export const requireAdmin: RequestHandler = (req, res, next) => {
  const user = (req as AuthenticatedRequest).user;
  if (!user || !isAdmin(user)) {
    res.status(403).json({ error: 'Admin role required' });
    return;
  }
  next();
};
