import type { Logger } from 'pino';

/**
 * Answers "may this caller use this document?". The rule itself lives in
 * document-service (DocumentService.can_access); collab-service only asks.
 */
export interface DocumentAccessChecker {
  canAccess(documentId: string, token: string): Promise<boolean>;
}

/** y-websocket room names are `document-<id>` (see client-app CollaborativeEditor). */
export const Y_WEBSOCKET_ROOM_PREFIX = 'document-';

/** Document id named by a y-websocket URL path, or null when the path names none. */
export function documentIdFromRoom(pathname: string): string | null {
  const room = decodeURIComponent(pathname.replace(/^\/+/, '').split('/')[0] ?? '');
  const documentId = room.startsWith(Y_WEBSOCKET_ROOM_PREFIX)
    ? room.slice(Y_WEBSOCKET_ROOM_PREFIX.length)
    : room;
  return documentId.length > 0 ? documentId : null;
}

interface AccessResponse {
  allowed?: boolean;
}

export class DocumentServiceAccessClient implements DocumentAccessChecker {
  constructor(
    private readonly baseUrl: string,
    private readonly logger: Logger,
    private readonly timeoutMs = 3000,
  ) {}

  async canAccess(documentId: string, token: string): Promise<boolean> {
    const url = `${this.baseUrl.replace(/\/+$/, '')}/api/v1/documents/${encodeURIComponent(
      documentId,
    )}/access`;

    try {
      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
        signal: AbortSignal.timeout(this.timeoutMs),
      });

      if (response.status !== 200) {
        this.logger.warn(
          { documentId, status: response.status },
          'document_access_check_denied',
        );
        return false;
      }

      const body = (await response.json()) as AccessResponse;
      return body.allowed === true;
    } catch (err) {
      // Fail closed: an unreachable document-service never grants access.
      this.logger.error({ err, documentId }, 'document_access_check_failed');
      return false;
    }
  }
}
