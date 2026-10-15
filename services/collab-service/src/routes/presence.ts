import { Router } from 'express';
import rateLimit from 'express-rate-limit';
import type { Logger } from 'pino';
import type { PresenceHandler } from '../handlers/presence';
import { createHttpAuthMiddleware, type AuthenticatedUser } from '../middleware/auth';
import type { DocumentAccessChecker } from '../services/document-access';

export function createPresenceRouter(
  presenceHandler: PresenceHandler,
  documentAccess: DocumentAccessChecker,
  jwtSecret: string,
  logger: Logger,
): Router {
  const router = Router();
  // Every presence request costs a document-service lookup per document, so cap it per client
  router.use(
    rateLimit({
      windowMs: 60_000,
      limit: 300,
      standardHeaders: 'draft-7',
      legacyHeaders: false,
    }),
  );
  router.use(createHttpAuthMiddleware(jwtSecret, logger));

  router.get('/documents/:id/presence', async (req, res) => {
    const documentId = req.params.id;
    const user = res.locals.user as AuthenticatedUser;
    if (
      !(await documentAccess.canAccess(user.userId, res.locals.accessToken, documentId))
    ) {
      // Same answer for "missing" and "not yours", so presence does not reveal which ids exist
      res.status(404).json({ error: 'Document not found' });
      return;
    }
    res.json(presenceHandler.getDocumentPresence(documentId));
  });

  // Active documents, limited to the ones the caller can open
  router.get('/documents', async (_req, res) => {
    const user = res.locals.user as AuthenticatedUser;
    const all = presenceHandler.getActiveDocuments();
    const allowed = await Promise.all(
      all.map((d) =>
        documentAccess.canAccess(user.userId, res.locals.accessToken, d.documentId),
      ),
    );
    const activeDocuments = all.filter((_d, i) => allowed[i]);
    res.json({ documents: activeDocuments, count: activeDocuments.length });
  });

  return router;
}
