import jwt from 'jsonwebtoken';
import type { Socket } from 'socket.io';
import type { ExtendedError } from 'socket.io/dist/namespace';
import type { Logger } from 'pino';
import type { NextFunction, Request, Response } from 'express';

export interface AuthenticatedUser {
  userId: string;
  email: string;
  displayName: string;
  roles: string[];
}

export interface AuthenticatedSocket extends Socket {
  user?: AuthenticatedUser;
  accessToken?: string;
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
  if (!decoded.sub) {
    throw new Error('Token has no subject');
  }
  return {
    userId: decoded.sub,
    email: decoded.email || '',
    displayName: decoded.name || decoded.display_name || 'Anonymous',
    roles: decoded.roles || [],
  };
}

export function extractBearerToken(header: string | undefined): string | undefined {
  if (!header?.startsWith('Bearer ')) return undefined;
  return header.slice('Bearer '.length).trim() || undefined;
}

export function createHttpAuthMiddleware(jwtSecret: string, logger: Logger) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const token = extractBearerToken(req.headers.authorization);
    if (!token) {
      res.status(401).json({ error: 'Authentication required' });
      return;
    }
    try {
      res.locals.user = verifyAccessToken(token, jwtSecret);
      res.locals.accessToken = token;
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
      (socket as AuthenticatedSocket).accessToken = token;

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
  return (socket as AuthenticatedSocket).accessToken;
}
