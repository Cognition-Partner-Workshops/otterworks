import type { Logger } from 'pino';
import type { AuthenticatedUser } from '../middleware/auth';

export interface DocumentAccess {
  /** The caller owns the document (document-service `owner_id`). */
  isOwner: boolean;
  /** The caller may change the document (updates, snapshots, comments). */
  canEdit: boolean;
}

export interface DocumentAccessChecker {
  /**
   * Resolve what `user` may do with `documentId`, or `null` when the document
   * does not exist or the user may not see it. Throws on upstream failures so
   * callers fail closed.
   */
  check(
    documentId: string,
    user: AuthenticatedUser,
    token: string,
  ): Promise<DocumentAccess | null>;
}

interface DocumentServiceAccessOptions {
  baseUrl: string;
  timeoutMs: number;
}

/**
 * Asks document-service whether the caller may read the document by replaying
 * the caller's own JWT against `GET /api/v1/documents/:id`, so the permission
 * model stays in one place (document-service) instead of being re-implemented
 * here.
 */
export class DocumentServiceAccessChecker implements DocumentAccessChecker {
  private baseUrl: string;
  private timeoutMs: number;
  private logger: Logger;

  constructor(options: DocumentServiceAccessOptions, logger: Logger) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, '');
    this.timeoutMs = options.timeoutMs;
    this.logger = logger;
  }

  async check(
    documentId: string,
    user: AuthenticatedUser,
    token: string,
  ): Promise<DocumentAccess | null> {
    const url = `${this.baseUrl}/api/v1/documents/${encodeURIComponent(documentId)}`;
    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-User-ID': user.userId,
        Accept: 'application/json',
      },
      signal: AbortSignal.timeout(this.timeoutMs),
    });

    if (response.status === 200) {
      const body = (await response.json()) as { owner_id?: string };
      const isOwner = String(body.owner_id ?? '') === user.userId;
      return { isOwner, canEdit: isOwner };
    }

    if (response.status >= 400 && response.status < 500) {
      this.logger.debug(
        { documentId, userId: user.userId, status: response.status },
        'document_access_denied_by_document_service',
      );
      return null;
    }

    throw new Error(`document-service responded ${response.status} for ${documentId}`);
  }
}
