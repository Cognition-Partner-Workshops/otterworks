import type { Logger } from 'pino';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isValidDocumentId(documentId: unknown): documentId is string {
  return typeof documentId === 'string' && UUID_PATTERN.test(documentId);
}

export interface DocumentAccessCheck {
  canAccess(documentId: string, userId: string, token: string): Promise<boolean>;
}

export interface DocumentAccessOptions {
  baseUrl: string;
  timeoutMs: number;
}

/**
 * Asks document-service whether the caller may open a document. document-service
 * is the source of truth for ownership; any non-2xx answer or transport error is
 * treated as a denial.
 */
export class DocumentServiceAccessChecker implements DocumentAccessCheck {
  constructor(
    private readonly options: DocumentAccessOptions,
    private readonly logger: Logger,
    private readonly fetchImpl: typeof fetch = fetch,
  ) {}

  async canAccess(documentId: string, userId: string, token: string): Promise<boolean> {
    if (!isValidDocumentId(documentId) || !token) return false;

    const url = `${this.options.baseUrl.replace(/\/+$/, '')}/api/v1/documents/${encodeURIComponent(documentId)}`;
    try {
      const response = await this.fetchImpl(url, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
          'X-User-ID': userId,
          Accept: 'application/json',
        },
        signal: AbortSignal.timeout(this.options.timeoutMs),
      });
      if (!response.ok) {
        this.logger.warn(
          { documentId, userId, status: response.status },
          'document_access_denied',
        );
      }
      return response.ok;
    } catch (err) {
      this.logger.error({ err, documentId, userId }, 'document_access_check_failed');
      return false;
    }
  }
}
