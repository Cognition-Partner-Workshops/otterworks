import type { IncomingMessage } from 'http';
import { verifyBearerToken } from '../middleware/auth';
import type { DocumentAccessChecker } from '../services/document-access';

const YJS_ROOM_PREFIX = 'document-';

export interface YjsUpgradeDecision {
  allowed: boolean;
  status: 101 | 401 | 403;
  reason?: string;
  userId?: string;
  documentId?: string;
}

/** The y-websocket room is the URL path, e.g. `/document-<id>?token=...`. */
export function documentIdFromYjsUrl(url: URL): string | null {
  let room: string;
  try {
    room = decodeURIComponent(url.pathname.replace(/^\/+/, ''));
  } catch {
    return null;
  }
  if (!room.startsWith(YJS_ROOM_PREFIX)) return null;
  return room.slice(YJS_ROOM_PREFIX.length) || null;
}

/**
 * Decides whether a y-websocket upgrade may proceed: the token must be valid and
 * its subject must be allowed to edit the document named in the URL.
 */
export async function authorizeYjsUpgrade(
  request: IncomingMessage,
  jwtSecret: string,
  documentAccess: DocumentAccessChecker,
): Promise<YjsUpgradeDecision> {
  const url = new URL(request.url || '', `http://${request.headers.host || 'localhost'}`);
  const token =
    url.searchParams.get('token') ||
    request.headers.authorization?.replace('Bearer ', '');

  const caller = verifyBearerToken(token, jwtSecret);
  if (!caller) {
    return {
      allowed: false,
      status: 401,
      reason: token ? 'invalid token' : 'no token',
    };
  }

  const documentId = documentIdFromYjsUrl(url);
  if (!documentId) {
    return {
      allowed: false,
      status: 403,
      reason: 'unknown room',
      userId: caller.userId,
    };
  }

  const access = await documentAccess.getAccess(documentId, caller.userId, caller.token);
  if (!access.canRead || !access.canEdit) {
    return {
      allowed: false,
      status: 403,
      reason: 'access denied',
      userId: caller.userId,
      documentId,
    };
  }

  return { allowed: true, status: 101, userId: caller.userId, documentId };
}
