import type { Logger } from 'pino';

export interface DocumentAccessOptions {
  documentServiceUrl: string;
  timeoutMs: number;
  cacheTtlMs: number;
  maxCacheEntries?: number;
}

type FetchFn = typeof fetch;

/**
 * Asks document-service whether a user may open a document, by calling
 * GET /api/v1/documents/{id} with the user's own JWT. Any non-2xx answer, or
 * an unreachable document-service, means no access.
 */
export class DocumentAccessChecker {
  private readonly cache = new Map<string, { allowed: boolean; expiresAt: number }>();
  private readonly baseUrl: string;
  private readonly maxCacheEntries: number;

  constructor(
    private readonly options: DocumentAccessOptions,
    private readonly logger: Logger,
    private readonly fetchFn: FetchFn = fetch,
  ) {
    this.baseUrl = options.documentServiceUrl.replace(/\/+$/, '');
    this.maxCacheEntries = options.maxCacheEntries ?? 10000;
  }

  async canAccess(userId: string, token: string, documentId: string): Promise<boolean> {
    if (!userId || !token || !documentId) return false;

    const key = `${userId}\u0000${documentId}`;
    const cached = this.cache.get(key);
    if (cached && cached.expiresAt > Date.now()) return cached.allowed;

    let allowed: boolean;
    try {
      const response = await this.fetchFn(
        `${this.baseUrl}/api/v1/documents/${encodeURIComponent(documentId)}`,
        {
          headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
          redirect: 'manual',
          signal: AbortSignal.timeout(this.options.timeoutMs),
        },
      );
      allowed = response.status >= 200 && response.status < 300;
      await response.body?.cancel().catch(() => undefined);
    } catch (err) {
      this.logger.warn(
        { documentId, userId, error: (err as Error).message },
        'document_access_check_failed',
      );
      return false;
    }

    this.remember(key, allowed);
    if (!allowed) {
      this.logger.warn({ documentId, userId }, 'document_access_denied');
    }
    return allowed;
  }

  private remember(key: string, allowed: boolean): void {
    if (this.options.cacheTtlMs <= 0) return;
    if (this.cache.size >= this.maxCacheEntries) {
      const oldest = this.cache.keys().next().value;
      if (oldest !== undefined) this.cache.delete(oldest);
    }
    this.cache.set(key, { allowed, expiresAt: Date.now() + this.options.cacheTtlMs });
  }
}
