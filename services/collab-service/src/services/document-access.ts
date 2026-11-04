import type { Logger } from 'pino';

export interface DocumentPrincipal {
  userId: string;
  token: string;
}

export interface DocumentAccessPolicy {
  canAccess(documentId: string, principal: DocumentPrincipal): Promise<boolean>;
}

export interface DocumentAccessCheckerOptions {
  documentServiceUrl: string;
  timeoutMs?: number;
  cacheTtlMs?: number;
  maxCacheEntries?: number;
}

const DOCUMENT_ID_PATTERN = /^[A-Za-z0-9_-]{1,128}$/;

export function isValidDocumentId(documentId: unknown): documentId is string {
  return typeof documentId === 'string' && DOCUMENT_ID_PATTERN.test(documentId);
}

/**
 * Asks document-service whether the caller may read a document, using the
 * caller's own token so document-service applies its ownership rules.
 * Fails closed: any non-2xx response or transport error denies access.
 */
export class DocumentAccessChecker implements DocumentAccessPolicy {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly cacheTtlMs: number;
  private readonly maxCacheEntries: number;
  private readonly cache = new Map<string, { allowed: boolean; expiresAt: number }>();
  private readonly logger: Logger;

  constructor(options: DocumentAccessCheckerOptions, logger: Logger) {
    this.baseUrl = options.documentServiceUrl.replace(/\/+$/, '');
    this.timeoutMs = options.timeoutMs ?? 3000;
    this.cacheTtlMs = options.cacheTtlMs ?? 10000;
    this.maxCacheEntries = options.maxCacheEntries ?? 10000;
    this.logger = logger;
  }

  async canAccess(documentId: string, principal: DocumentPrincipal): Promise<boolean> {
    if (!isValidDocumentId(documentId) || !principal.token || !principal.userId) {
      return false;
    }

    const cacheKey = `${principal.userId}\u0000${documentId}`;
    const now = Date.now();
    const cached = this.cache.get(cacheKey);
    if (cached && cached.expiresAt > now) {
      return cached.allowed;
    }

    let allowed: boolean;
    try {
      const response = await fetch(
        `${this.baseUrl}/api/v1/documents/${encodeURIComponent(documentId)}`,
        {
          method: 'GET',
          headers: {
            Accept: 'application/json',
            Authorization: `Bearer ${principal.token}`,
            'X-User-ID': principal.userId,
          },
          signal: AbortSignal.timeout(this.timeoutMs),
        },
      );
      allowed = response.ok;
      await response.body?.cancel().catch(() => undefined);
    } catch (err) {
      this.logger.warn(
        { documentId, userId: principal.userId, error: (err as Error).message },
        'document_access_check_failed',
      );
      return false;
    }

    this.remember(cacheKey, allowed, now);
    if (!allowed) {
      this.logger.warn(
        { documentId, userId: principal.userId },
        'document_access_denied',
      );
    }
    return allowed;
  }

  private remember(cacheKey: string, allowed: boolean, now: number): void {
    if (this.cache.size >= this.maxCacheEntries) {
      for (const [key, entry] of this.cache) {
        if (entry.expiresAt <= now) this.cache.delete(key);
      }
      if (this.cache.size >= this.maxCacheEntries) this.cache.clear();
    }
    this.cache.set(cacheKey, { allowed, expiresAt: now + this.cacheTtlMs });
  }
}
