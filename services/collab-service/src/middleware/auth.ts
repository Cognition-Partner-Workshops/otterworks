import jwt from 'jsonwebtoken';
import type { Request, Response, NextFunction } from 'express';
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
}

export interface AuthenticatedRequest extends Request {
  user?: AuthenticatedUser;
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

export function verifyAccessToken(token: string, jwtSecret: string): AuthenticatedUser {
  const decoded = jwt.verify(token, jwtSecret) as JwtPayload;
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
      socket.handshake.headers?.authorization?.replace('Bearer ', '');

    if (!token) {
      logger.warn({ socketId: socket.id }, 'connection_rejected: no token provided');
      next(new Error('Authentication required'));
      return;
    }

    try {
      const user = verifyAccessToken(token, jwtSecret);
      (socket as AuthenticatedSocket).user = user;

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

/** Express middleware: same JWT verification as the Socket.IO join path, for HTTP routes. */
export function createHttpAuthMiddleware(jwtSecret: string, logger: Logger) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const token = req.headers.authorization?.replace('Bearer ', '');

    if (!token) {
      logger.warn({ path: req.path }, 'http_request_rejected: no token provided');
      res.status(401).json({ error: 'Authentication required' });
      return;
    }

    try {
      (req as AuthenticatedRequest).user = verifyAccessToken(token, jwtSecret);
      next();
    } catch (err) {
      logger.warn(
        { path: req.path, error: (err as Error).message },
        'http_request_rejected: invalid token',
      );
      res.status(401).json({ error: 'Invalid or expired token' });
    }
  };
}

export function extractUserFromRequest(req: Request): AuthenticatedUser | undefined {
  return (req as AuthenticatedRequest).user;
}
