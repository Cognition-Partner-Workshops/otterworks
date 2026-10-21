import { Router } from 'express';
import type { Logger } from 'pino';
import { createHttpAuthMiddleware, extractUserFromRequest } from '../middleware/auth';
import { PresenceHandler } from '../handlers/presence';

/**
 * HTTP presence routes. Every route requires the caller's JWT (the same
 * verification the Socket.IO join path uses) and is scoped to documents the
 * caller is currently a participant of, so no cross-tenant document IDs or
 * presence details are exposed.
 */
export function createPresenceRouter(
  presenceHandler: PresenceHandler,
  jwtSecret: string,
  logger: Logger,
): Router {
  const router = Router();
  router.use(createHttpAuthMiddleware(jwtSecret, logger));

  router.get('/api/v1/collab/documents/:id/presence', (req, res) => {
    const documentId = req.params.id;
    const user = extractUserFromRequest(req);

    if (!user || !presenceHandler.canUserAccessDocument(documentId, user.userId)) {
      logger.warn({ documentId, userId: user?.userId }, 'presence_access_denied');
      res.status(403).json({ error: 'Forbidden' });
      return;
    }

    res.json(presenceHandler.getDocumentPresence(documentId));
  });

  router.get('/api/v1/collab/documents', (req, res) => {
    const user = extractUserFromRequest(req);
    if (!user) {
      res.status(401).json({ error: 'Authentication required' });
      return;
    }

    const activeDocuments = presenceHandler.getActiveDocumentsForUser(user.userId);
    res.json({ documents: activeDocuments, count: activeDocuments.length });
  });

  return router;
}
