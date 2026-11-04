import express from 'express';
import { createServer } from 'http';
import { Server as SocketIOServer } from 'socket.io';
import { WebSocketServer } from 'ws';
import cors from 'cors';
import helmet from 'helmet';
import pino from 'pino';
import { loadConfig } from './config';
import { MetricsCollector } from './metrics';
import {
  createAuthMiddleware,
  extractBearerToken,
  verifyUserToken,
  type AuthenticatedUser,
} from './middleware/auth';
import { RedisAdapter } from './services/redis-adapter';
import { DocumentStore } from './services/document-store';
import { AwarenessService } from './services/awareness';
import { PresenceHandler } from './handlers/presence';
import { setupCollaborationHandlers } from './handlers/collaboration';
import {
  DocumentAccessChecker,
  type DocumentPrincipal,
} from './services/document-access';

// eslint-disable-next-line @typescript-eslint/no-var-requires
const { setupWSConnection } = require('y-websocket/bin/utils');

const config = loadConfig();

const logger = pino({
  level: config.logLevel,
  transport:
    process.env.NODE_ENV !== 'production'
      ? { target: 'pino-pretty', options: { colorize: true } }
      : undefined,
  base: { service: 'collab-service' },
});

const app = express();
const httpServer = createServer(app);
const metrics = new MetricsCollector();
const accessPolicy = new DocumentAccessChecker(
  {
    documentServiceUrl: config.documentService.url,
    timeoutMs: config.documentService.timeoutMs,
    cacheTtlMs: config.documentService.accessCacheTtlMs,
  },
  logger,
);

function authenticateHttpRequest(
  req: express.Request,
): { user: AuthenticatedUser; principal: DocumentPrincipal } | null {
  const token = extractBearerToken(req.headers.authorization);
  if (!token) return null;
  try {
    const user = verifyUserToken(token, config.jwt.secret);
    return { user, principal: { userId: user.userId, token } };
  } catch {
    return null;
  }
}

// Middleware
app.use(helmet());
app.use(
  cors({
    origin: config.cors.origins,
    credentials: true,
  }),
);
app.use(express.json());

// Health check
app.get('/health', async (_req, res) => {
  const redisHealthy = await redisAdapter.ping();
  const status = redisHealthy ? 'healthy' : 'degraded';
  res.status(redisHealthy ? 200 : 503).json({
    status,
    service: 'collab-service',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    redis: redisHealthy ? 'connected' : 'disconnected',
    activeDocuments: collabManager?.getDocumentCount() ?? 0,
  });
});

// Prometheus metrics endpoint
app.get('/metrics', async (_req, res) => {
  try {
    const metricsOutput = await metrics.getMetrics();
    res.type(metrics.getContentType()).send(metricsOutput);
  } catch (err) {
    logger.error({ err }, 'metrics_collection_failed');
    res.status(500).send('Error collecting metrics');
  }
});

// Presence endpoint
app.get('/api/v1/collab/documents/:id/presence', async (req, res) => {
  const auth = authenticateHttpRequest(req);
  if (!auth) {
    res.status(401).json({ error: 'Authentication required' });
    return;
  }
  const documentId = req.params.id;
  if (!(await accessPolicy.canAccess(documentId, auth.principal))) {
    res.status(404).json({ error: 'Document not found' });
    return;
  }
  res.json(presenceHandler.getDocumentPresence(documentId));
});

// Active documents listing, limited to documents the caller can access
app.get('/api/v1/collab/documents', async (req, res) => {
  const auth = authenticateHttpRequest(req);
  if (!auth) {
    res.status(401).json({ error: 'Authentication required' });
    return;
  }
  const activeDocuments = presenceHandler.getActiveDocuments();
  const accessible = await Promise.all(
    activeDocuments.map((doc) => accessPolicy.canAccess(doc.documentId, auth.principal)),
  );
  const documents = activeDocuments.filter((_doc, i) => accessible[i]);
  res.json({ documents, count: documents.length });
});

// Socket.IO server
const io = new SocketIOServer(httpServer, {
  cors: {
    origin: config.cors.origins,
    credentials: true,
  },
  pingInterval: 25000,
  pingTimeout: 20000,
  // Non-Socket.IO upgrades are owned by the y-websocket handler below, whose
  // async access check can outlast Engine.IO's default 1s destroy timer.
  destroyUpgrade: false,
});

// JWT auth middleware for WebSocket
io.use(createAuthMiddleware(config.jwt.secret, logger));

// Initialize services
const redisAdapter = new RedisAdapter(
  {
    host: config.redis.host,
    port: config.redis.port,
    password: config.redis.password,
    db: config.redis.db,
    keyPrefix: config.redis.keyPrefix,
  },
  logger,
);

const documentStore = new DocumentStore(redisAdapter, logger, {
  documentTtl: config.persistence.documentTtlSeconds,
  snapshotTtl: config.persistence.snapshotTtlSeconds,
  maxSnapshots: config.persistence.maxSnapshotsPerDocument,
});

const awareness = new AwarenessService(logger);
const presenceHandler = new PresenceHandler(awareness, logger);

// Setup collaboration handlers
const collabManager = setupCollaborationHandlers(
  io,
  documentStore,
  awareness,
  presenceHandler,
  accessPolicy,
  metrics,
  logger,
  config.persistence.intervalMs,
  config.persistence.snapshotIntervalMs,
);

// y-websocket server for TipTap/Yjs collaborative editing
const wss = new WebSocketServer({ noServer: true });
const YWS_ROOM_PREFIX = 'document-';

function rejectUpgrade(socket: import('stream').Duplex, status: string): void {
  socket.write(`HTTP/1.1 ${status}\r\n\r\n`);
  socket.destroy();
}

// Route WebSocket upgrades: Socket.IO paths go to Socket.IO, all others to y-websocket
httpServer.on('upgrade', async (request, socket, head) => {
  if (request.url?.startsWith('/socket.io/')) {
    // Socket.IO handles its own upgrades via its internal listener
    return;
  }

  // JWT authentication for y-websocket connections
  const url = new URL(request.url || '', `http://${request.headers.host}`);
  const token =
    url.searchParams.get('token') || extractBearerToken(request.headers.authorization);

  if (!token) {
    logger.warn('y-websocket_connection_rejected: no token');
    rejectUpgrade(socket, '401 Unauthorized');
    return;
  }

  let user: AuthenticatedUser;
  try {
    user = verifyUserToken(token, config.jwt.secret);
  } catch {
    logger.warn('y-websocket_connection_rejected: invalid token');
    rejectUpgrade(socket, '401 Unauthorized');
    return;
  }

  // Same room-name derivation y-websocket uses; passed explicitly below so the
  // authorized room is the one the connection is attached to.
  const docName = (request.url || '').slice(1).split('?')[0];
  const documentId = docName.startsWith(YWS_ROOM_PREFIX)
    ? docName.slice(YWS_ROOM_PREFIX.length)
    : '';
  const allowed = await accessPolicy.canAccess(documentId, {
    userId: user.userId,
    token,
  });
  if (!allowed) {
    logger.warn(
      { userId: user.userId, documentId },
      'y-websocket_connection_rejected: access denied',
    );
    rejectUpgrade(socket, '403 Forbidden');
    return;
  }
  if (socket.destroyed) return;

  wss.handleUpgrade(request, socket, head, (ws) => {
    setupWSConnection(ws, request, { docName });
    logger.info({ documentId, userId: user.userId }, 'y-websocket_client_connected');
  });
});

// Start presence cleanup with document eviction callback
const presenceCleanupTimer = presenceHandler.startCleanupInterval(
  io,
  60000,
  300000,
  (documentId: string) => {
    collabManager.persistAndCleanupDocument(documentId).catch((err) => {
      logger.error({ err, documentId }, 'stale_cleanup_document_eviction_failed');
    });
  },
);

// Start server
async function start(): Promise<void> {
  try {
    await redisAdapter.connect();
    logger.info('redis_connected');
  } catch (err) {
    logger.warn({ err }, 'redis_connection_failed, starting without Redis persistence');
  }

  httpServer.listen(config.httpPort, '0.0.0.0', () => {
    logger.info({ port: config.httpPort }, 'collaboration_service_started');
  });
}

// Graceful shutdown
async function shutdown(signal: string): Promise<void> {
  logger.info({ signal }, 'shutdown_initiated');

  clearInterval(presenceCleanupTimer);
  await collabManager.stop();

  httpServer.close(() => {
    redisAdapter.disconnect();
    logger.info('collaboration_service_stopped');
    process.exit(0);
  });

  // Force exit after 10 seconds
  setTimeout(() => {
    logger.error('forced_shutdown_after_timeout');
    process.exit(1);
  }, 10000);
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

start().catch((err) => {
  logger.fatal({ err }, 'startup_failed');
  process.exit(1);
});
