import type { Logger } from 'pino';
import {
  extractBearerToken,
  verifyAccessToken,
  type AuthenticatedUser,
} from '../middleware/auth';
import type { DocumentAccessChecker } from './document-access';

const YJS_ROOM_PREFIX = 'document-';

export type YjsUpgradeStatus = 200 | 401 | 403;

/**
 * Decides whether a y-websocket upgrade may proceed. y-websocket names the room after
 * the URL path and the editor uses `document-<id>`, so the caller must hold a valid JWT
 * and document-service must grant that user access to <id>.
 */
export async function authorizeYjsUpgrade(
  rawUrl: string,
  authorization: string | undefined,
  jwtSecret: string,
  documentAccess: DocumentAccessChecker,
  logger: Logger,
): Promise<YjsUpgradeStatus> {
  const url = new URL(rawUrl, 'http://collab.local');
  const token = url.searchParams.get('token') || extractBearerToken(authorization);
  if (!token) {
    logger.warn('y-websocket_connection_rejected: no token');
    return 401;
  }

  let user: AuthenticatedUser;
  try {
    user = verifyAccessToken(token, jwtSecret);
  } catch {
    logger.warn('y-websocket_connection_rejected: invalid token');
    return 401;
  }

  const roomName = rawUrl.slice(1).split('?')[0];
  let documentId = '';
  if (roomName.startsWith(YJS_ROOM_PREFIX)) {
    try {
      documentId = decodeURIComponent(roomName.slice(YJS_ROOM_PREFIX.length));
    } catch {
      documentId = '';
    }
  }
  if (!documentId || documentId.includes('/')) {
    logger.warn({ userId: user.userId }, 'y-websocket_connection_rejected: unknown room');
    return 403;
  }

  if (!(await documentAccess.canAccess(user.userId, token, documentId))) {
    logger.warn(
      { userId: user.userId, documentId },
      'y-websocket_connection_rejected: no access',
    );
    return 403;
  }
  return 200;
}
