import { Router, type Request, type Response, type NextFunction } from 'express';
import rateLimit from 'express-rate-limit';
import type { Logger } from 'pino';
import { verifyBearerToken, type VerifiedToken } from '../middleware/auth';
import type { PresenceHandler } from '../handlers/presence';
import type { DocumentAccessChecker } from '../services/document-access';

export interface CollabApiDeps {
  jwtSecret: string;
  presenceHandler: PresenceHandler;
  documentAccess: DocumentAccessChecker;
  logger: Logger;
  rateLimitPerMinute?: number;
}

interface AuthenticatedRequest extends Request {
  caller?: VerifiedToken;
}

export function createCollabApiRouter(deps: CollabApiDeps): Router {
  const { jwtSecret, presenceHandler, documentAccess, logger } = deps;
  const router = Router();

  function callerOf(req: Request): VerifiedToken | null {
    const header = req.headers.authorization;
    const token = header?.startsWith('Bearer ') ? header.slice('Bearer '.length) : null;
    return verifyBearerToken(token, jwtSecret);
  }

  // Each request can fan out to document-service, so cap it per user. Keyed on the
  // verified subject so a fresh token for the same user does not reset the budget.
  router.use(
    rateLimit({
      windowMs: 60_000,
      limit: deps.rateLimitPerMinute ?? 120,
      standardHeaders: true,
      legacyHeaders: false,
      keyGenerator: (req) => {
        const caller = callerOf(req);
        return caller ? `user:${caller.userId}` : `ip:${req.ip ?? 'unknown'}`;
      },
      message: { error: 'Too many requests' },
    }),
  );

  router.use((req: AuthenticatedRequest, res: Response, next: NextFunction) => {
    const caller = callerOf(req);
    if (!caller) {
      res.status(401).json({ error: 'Authentication required' });
      return;
    }
    req.caller = caller;
    next();
  });

  router.get('/documents/:id/presence', async (req: AuthenticatedRequest, res) => {
    const caller = req.caller as VerifiedToken;
    const documentId = req.params.id;
    const access = await documentAccess.getAccess(
      documentId,
      caller.userId,
      caller.token,
    );
    if (!access.canRead) {
      logger.warn({ userId: caller.userId }, 'presence_request_denied');
      // Same answer for "no such document" and "not yours" so ids cannot be probed.
      res.status(404).json({ error: 'Document not found' });
      return;
    }
    res.json(presenceHandler.getDocumentPresence(documentId));
  });

  router.get('/documents', async (req: AuthenticatedRequest, res) => {
    const caller = req.caller as VerifiedToken;
    const activeDocuments = presenceHandler.getActiveDocuments();
    const accessResults = await Promise.all(
      activeDocuments.map((entry) =>
        documentAccess.getAccess(entry.documentId, caller.userId, caller.token),
      ),
    );
    const visibleDocuments = activeDocuments.filter(
      (_entry, index) => accessResults[index].canRead,
    );
    res.json({ documents: visibleDocuments, count: visibleDocuments.length });
  });

  return router;
}
