import type { Socket } from 'socket.io';
import type { Logger } from 'pino';

export interface DocumentAccessRequest {
  documentId: string;
  userId: string;
  token: string;
}

export interface DocumentAccessChecker {
  canAccess(request: DocumentAccessRequest): Promise<boolean>;
}

export interface HttpDocumentAccessCheckerOptions {
  baseUrl: string;
  timeoutMs: number;
}

const YJS_ROOM_PREFIX = 'document-';

/**
 * Asks document-service whether the caller may open a document by fetching it
 * with the caller's own credentials. document-service only returns 200 for
 * documents the caller is allowed to read; anything else (401/403/404, 5xx,
 * network errors, timeouts) is treated as a denial so access fails closed.
 */
export class HttpDocumentAccessChecker implements DocumentAccessChecker {
  private readonly baseUrl: string;

  constructor(
    private readonly options: HttpDocumentAccessCheckerOptions,
    private readonly logger: Logger,
  ) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, '');
  }

  async canAccess({
    documentId,
    userId,
    token,
  }: DocumentAccessRequest): Promise<boolean> {
    if (!isValidDocumentId(documentId) || !token || !userId) {
      return false;
    }

    const url = `${this.baseUrl}/api/v1/documents/${encodeURIComponent(documentId)}`;
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
          'X-User-ID': userId,
          Accept: 'application/json',
        },
        signal: AbortSignal.timeout(this.options.timeoutMs),
      });
      if (response.ok) {
        return true;
      }
      this.logger.warn(
        { documentId, userId, status: response.status },
        'document_access_denied',
      );
      return false;
    } catch (err) {
      this.logger.error({ err, documentId, userId }, 'document_access_check_failed');
      return false;
    }
  }
}

export function isValidDocumentId(documentId: unknown): documentId is string {
  return (
    typeof documentId === 'string' &&
    documentId.length > 0 &&
    documentId.length <= 128 &&
    /^[A-Za-z0-9_-]+$/.test(documentId)
  );
}

export function extractSocketToken(socket: Socket): string {
  const token =
    socket.handshake.auth?.token ||
    socket.handshake.headers?.authorization?.replace('Bearer ', '');
  return typeof token === 'string' ? token : '';
}

/** Maps a y-websocket room path (`/document-<id>`) to its document ID. */
export function documentIdFromYjsRoom(pathname: string): string | null {
  let roomName: string;
  try {
    roomName = decodeURIComponent(pathname.replace(/^\/+/, ''));
  } catch {
    return null;
  }
  if (!roomName.startsWith(YJS_ROOM_PREFIX)) {
    return null;
  }
  const documentId = roomName.slice(YJS_ROOM_PREFIX.length);
  return isValidDocumentId(documentId) ? documentId : null;
}
