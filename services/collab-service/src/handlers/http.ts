import { Router } from 'express';
import type { IncomingMessage } from 'http';
import type { Logger } from 'pino';
import {
  createHttpAuthMiddleware,
  extractBearerToken,
  verifyToken,
  type AuthenticatedUser,
} from '../middleware/auth';
import {
  permissionSatisfies,
  type DocumentAccessChecker,
} from '../services/document-access';
import type { AwarenessService } from '../services/awareness';
import type { PresenceHandler } from './presence';

export interface CollabHttpDeps {
  jwtSecret: string;
  documentAccess: DocumentAccessChecker;
  awareness: AwarenessService;
  presenceHandler: PresenceHandler;
  logger: Logger;
}

/**
 * REST surface under /api/v1/collab. Every route needs the caller's bearer token;
 * the listing is scoped to documents the caller is present in, and presence for a
 * document is only returned when document-service says the caller may view it.
 */
export function createCollabRouter(deps: CollabHttpDeps): Router {
  const { jwtSecret, documentAccess, awareness, presenceHandler, logger } = deps;
  const router = Router();

  router.use(createHttpAuthMiddleware(jwtSecret, logger));

  router.get('/documents', (_req, res) => {
    const user = res.locals.user as AuthenticatedUser;
    const documents = presenceHandler
      .getActiveDocuments()
      .filter(({ documentId }) =>
        awareness.getDocumentUsers(documentId).some((u) => u.userId === user.userId),
      );
    res.json({ documents, count: documents.length });
  });

  router.get('/documents/:id/presence', async (req, res) => {
    const user = res.locals.user as AuthenticatedUser;
    const token = res.locals.token as string;
    const documentId = req.params.id;
    try {
      const permission = await documentAccess.checkAccess({ documentId, user, token });
      if (!permissionSatisfies(permission ?? undefined, 'view')) {
        res.status(404).json({ error: 'Document not found' });
        return;
      }
    } catch (err) {
      logger.error({ err, documentId }, 'presence_access_check_failed');
      res.status(503).json({ error: 'Document access check unavailable' });
      return;
    }
    res.json(presenceHandler.getDocumentPresence(documentId));
  });

  return router;
}

export type UpgradeDecision =
  | { allowed: true; user: AuthenticatedUser; documentId: string }
  | { allowed: false; status: 401 | 403 | 503; reason: string };

/** y-websocket rooms are named `document-<id>`; the bare id is accepted too. */
export function documentIdFromRoom(pathname: string): string {
  const room = decodeURIComponent(pathname.replace(/^\/+/, '').split('/')[0] ?? '');
  return room.startsWith('document-') ? room.slice('document-'.length) : room;
}

/**
 * Authorizes a raw y-websocket upgrade. y-websocket syncs in both directions, so
 * only callers document-service grants `edit` on the room's document may connect.
 */
export async function authorizeYWebsocketUpgrade(
  request: IncomingMessage,
  deps: Pick<CollabHttpDeps, 'jwtSecret' | 'documentAccess' | 'logger'>,
): Promise<UpgradeDecision> {
  const url = new URL(request.url || '', `http://${request.headers.host || 'localhost'}`);
  const token = url.searchParams.get('token') || extractBearerToken(request);
  if (!token) {
    return { allowed: false, status: 401, reason: 'no token' };
  }

  let user: AuthenticatedUser;
  try {
    user = verifyToken(token, deps.jwtSecret);
  } catch {
    return { allowed: false, status: 401, reason: 'invalid token' };
  }

  const documentId = documentIdFromRoom(url.pathname);
  try {
    const permission = await deps.documentAccess.checkAccess({ documentId, user, token });
    if (!permissionSatisfies(permission ?? undefined, 'edit')) {
      return { allowed: false, status: 403, reason: 'access denied' };
    }
  } catch (err) {
    deps.logger.error({ err, documentId }, 'y_websocket_access_check_failed');
    return { allowed: false, status: 503, reason: 'access check unavailable' };
  }

  return { allowed: true, user, documentId };
}
