import type { Logger } from 'pino';

export interface DocumentAccess {
  canRead: boolean;
  canEdit: boolean;
}

export const NO_ACCESS: DocumentAccess = Object.freeze({
  canRead: false,
  canEdit: false,
});

export interface DocumentAccessChecker {
  getAccess(documentId: string, userId: string, token: string): Promise<DocumentAccess>;
}

export interface DocumentAccessOptions {
  documentServiceUrl: string;
  timeoutMs: number;
  cacheTtlMs: number;
  fetchImpl?: typeof fetch;
}

const DOCUMENT_ID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const MAX_CACHE_ENTRIES = 10000;

export function isValidDocumentId(documentId: unknown): documentId is string {
  return typeof documentId === 'string' && DOCUMENT_ID_PATTERN.test(documentId);
}

/**
 * Asks document-service, as the caller, whether the caller may open a document.
 * Any answer other than a successful read is treated as no access.
 */
export class DocumentAccessService implements DocumentAccessChecker {
  private options: DocumentAccessOptions;
  private logger: Logger;
  private cache: Map<string, { access: DocumentAccess; expiresAt: number }> = new Map();

  constructor(options: DocumentAccessOptions, logger: Logger) {
    this.options = options;
    this.logger = logger;
  }

  async getAccess(
    documentId: string,
    userId: string,
    token: string,
  ): Promise<DocumentAccess> {
    if (!isValidDocumentId(documentId) || !userId || !token) {
      return NO_ACCESS;
    }

    const cacheKey = `${userId}:${documentId.toLowerCase()}`;
    const cached = this.cache.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) {
      return cached.access;
    }

    const access = await this.fetchAccess(documentId, userId, token);
    if (access) {
      this.remember(cacheKey, access);
      return access;
    }
    return NO_ACCESS;
  }

  /** Returns null when document-service gave no usable answer (not cached). */
  private async fetchAccess(
    documentId: string,
    userId: string,
    token: string,
  ): Promise<DocumentAccess | null> {
    const fetchImpl = this.options.fetchImpl ?? fetch;
    const baseUrl = this.options.documentServiceUrl.replace(/\/+$/, '');
    const url = `${baseUrl}/api/v1/documents/${encodeURIComponent(documentId)}`;

    try {
      const response = await fetchImpl(url, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
          'X-User-ID': userId,
          Accept: 'application/json',
        },
        signal: AbortSignal.timeout(this.options.timeoutMs),
      });

      if (response.status === 200) {
        // document-service only returns a document to a caller who owns it,
        // and owners may edit.
        return { canRead: true, canEdit: true };
      }
      if ([401, 403, 404, 422].includes(response.status)) {
        return NO_ACCESS;
      }
      this.logger.error(
        { documentId, userId, status: response.status },
        'document_access_check_unexpected_status',
      );
      return null;
    } catch (err) {
      this.logger.error({ err, documentId, userId }, 'document_access_check_failed');
      return null;
    }
  }

  private remember(cacheKey: string, access: DocumentAccess): void {
    if (this.options.cacheTtlMs <= 0) return;
    if (this.cache.size >= MAX_CACHE_ENTRIES) {
      this.cache.clear();
    }
    this.cache.set(cacheKey, {
      access,
      expiresAt: Date.now() + this.options.cacheTtlMs,
    });
  }
}
