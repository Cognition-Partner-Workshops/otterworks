import type { Logger } from 'pino';

/**
 * Decides whether the holder of `token` may open `documentId`. The document
 * service owns document ownership, so the check asks it directly with the
 * caller's own credentials.
 */
export type DocumentAccessChecker = (
  documentId: string,
  token: string | undefined,
) => Promise<boolean>;

export function createDocumentServiceAccessChecker(
  documentServiceUrl: string,
  logger: Logger,
  timeoutMs = 5000,
): DocumentAccessChecker {
  const base = documentServiceUrl.replace(/\/+$/, '');
  return async (documentId, token) => {
    if (!token || !documentId) return false;
    try {
      const res = await fetch(
        `${base}/api/v1/documents/${encodeURIComponent(documentId)}`,
        {
          headers: { Authorization: `Bearer ${token}` },
          signal: AbortSignal.timeout(timeoutMs),
        },
      );
      return res.ok;
    } catch (err) {
      logger.warn({ err, documentId }, 'document_access_check_failed');
      return false;
    }
  };
}
