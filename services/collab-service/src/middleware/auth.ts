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
  token?: string;
  authorizedDocuments?: Set<string>;
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
      const decoded = jwt.verify(token, jwtSecret) as JwtPayload;

      const authSocket = socket as AuthenticatedSocket;
      authSocket.user = {
        userId: decoded.sub,
        email: decoded.email || '',
        displayName: decoded.name || decoded.display_name || 'Anonymous',
        roles: decoded.roles || [],
      };
      authSocket.token = token;
      authSocket.authorizedDocuments = new Set();

      logger.debug(
        { socketId: socket.id, userId: decoded.sub },
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

/** Record that join-document authorized this socket for a document. */
export function grantDocumentAccess(socket: Socket, documentId: string): void {
  const authSocket = socket as AuthenticatedSocket;
  authSocket.authorizedDocuments ??= new Set();
  authSocket.authorizedDocuments.add(documentId);
}

export function revokeDocumentAccess(socket: Socket, documentId: string): void {
  (socket as AuthenticatedSocket).authorizedDocuments?.delete(documentId);
}

/** True only for documents this socket joined through an authorized join-document. */
export function hasDocumentAccess(socket: Socket, documentId: string): boolean {
  return (socket as AuthenticatedSocket).authorizedDocuments?.has(documentId) ?? false;
}
