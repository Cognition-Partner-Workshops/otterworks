import type { Logger } from 'pino';
import type { AuthenticatedUser } from '../middleware/auth';

/** What the caller may do with a document once document-service has vouched for them. */
export type DocumentPermission = 'view' | 'edit';

export interface AccessRequest {
  documentId: string;
  user: AuthenticatedUser;
  /** The caller's own bearer token, forwarded so document-service applies its own ownership rules. */
  token: string;
  /** Read-only share-link token minted by document-service; grants `view` to non-owners. */
  shareToken?: string;
}

export interface DocumentAccessChecker {
  /** Resolves the caller's permission on the document, or `null` when they have none. */
  checkAccess(request: AccessRequest): Promise<DocumentPermission | null>;
}

export class DocumentAccessError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DocumentAccessError';
  }
}

export interface DocumentAccessOptions {
  baseUrl: string;
  timeoutMs: number;
}

interface DocumentBody {
  owner_id?: string;
  permission?: string;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Asks document-service whether the caller may see a document. The caller's own
 * credentials are forwarded, so the decision is document-service's owner check
 * (or share-link check) rather than anything this service trusts from the client.
 * Any failure to get a definitive answer denies access.
 */
export class HttpDocumentAccessChecker implements DocumentAccessChecker {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly logger: Logger;

  constructor(options: DocumentAccessOptions, logger: Logger) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, '');
    this.timeoutMs = options.timeoutMs;
    this.logger = logger;
  }

  async checkAccess(request: AccessRequest): Promise<DocumentPermission | null> {
    const { documentId, user, token, shareToken } = request;
    if (!UUID_PATTERN.test(documentId)) {
      return null;
    }

    const owned = await this.fetchJson(`/api/v1/documents/${documentId}`, {
      Authorization: `Bearer ${token}`,
      'X-User-ID': user.userId,
    });
    if (owned) {
      return permissionFromBody(owned, user.userId);
    }

    if (shareToken) {
      const shared = await this.fetchJson(
        `/api/v1/documents/shared?document_id=${encodeURIComponent(documentId)}&token=${encodeURIComponent(shareToken)}`,
        {},
      );
      if (shared) return 'view';
    }

    return null;
  }

  private async fetchJson(
    path: string,
    headers: Record<string, string>,
  ): Promise<DocumentBody | null> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        headers: { Accept: 'application/json', ...headers },
        signal: controller.signal,
      });
      if (response.status === 200) {
        return (await response.json()) as DocumentBody;
      }
      if ([401, 403, 404, 422].includes(response.status)) {
        return null;
      }
      throw new DocumentAccessError(`document-service returned ${response.status}`);
    } catch (err) {
      if (err instanceof DocumentAccessError) throw err;
      this.logger.error({ err, path }, 'document_access_check_failed');
      throw new DocumentAccessError('document-service unreachable');
    } finally {
      clearTimeout(timer);
    }
  }
}

function permissionFromBody(body: DocumentBody, userId: string): DocumentPermission {
  if (body.permission === 'view' || body.permission === 'edit') {
    return body.permission;
  }
  return body.owner_id === userId ? 'edit' : 'view';
}

/** Allows only the document the caller may `view` or `edit` to be written by `edit` holders. */
export function permissionSatisfies(
  granted: DocumentPermission | undefined,
  required: DocumentPermission,
): boolean {
  if (!granted) return false;
  return required === 'view' || granted === 'edit';
}
