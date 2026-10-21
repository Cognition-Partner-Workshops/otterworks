import { Server as SocketIOServer, Socket } from 'socket.io';
import type { Logger } from 'pino';
import * as Y from 'yjs';
import { DocumentStore } from '../services/document-store';
import { AwarenessService, type CursorPosition } from '../services/awareness';
import { extractUserFromSocket } from '../middleware/auth';
import { MetricsCollector } from '../metrics';
import { PresenceHandler } from './presence';
import { DocRegistry } from '../services/doc-registry';
import { PersistenceScheduler } from '../services/persistence-scheduler';
import { CommentHandler } from './comments';
import { SnapshotHandler } from './snapshots';

export type { CommentAnnotation } from './comments';

export interface CollaborationDeps {
  io: SocketIOServer;
  documentStore: DocumentStore;
  awareness: AwarenessService;
  presenceHandler: PresenceHandler;
  metrics: MetricsCollector;
  logger: Logger;
  persistIntervalMs: number;
  snapshotIntervalMs: number;
}

export class CollaborationManager {
  private deps: CollaborationDeps;
  private registry: DocRegistry;
  private persistence: PersistenceScheduler;
  private comments: CommentHandler;
  private snapshots: SnapshotHandler;

  constructor(deps: CollaborationDeps) {
    this.deps = deps;
    this.registry = new DocRegistry({
      documentStore: deps.documentStore,
      metrics: deps.metrics,
    });
    this.persistence = new PersistenceScheduler({
      registry: this.registry,
      documentStore: deps.documentStore,
      metrics: deps.metrics,
      logger: deps.logger,
      persistIntervalMs: deps.persistIntervalMs,
      snapshotIntervalMs: deps.snapshotIntervalMs,
      hasActiveUsers: (documentId) => deps.awareness.getDocumentUserCount(documentId) > 0,
    });
    this.comments = new CommentHandler({ metrics: deps.metrics });
    this.snapshots = new SnapshotHandler({
      registry: this.registry,
      documentStore: deps.documentStore,
      logger: deps.logger,
    });
  }

  getDocument(documentId: string): Y.Doc | undefined {
    return this.registry.get(documentId);
  }

  getDocumentCount(): number {
    return this.registry.size;
  }

  start(): void {
    const { io, logger } = this.deps;

    io.on('connection', (socket: Socket) => {
      this.deps.metrics.activeConnections.inc();
      logger.info({ socketId: socket.id }, 'client_connected');

      this.registerSocketHandlers(socket);

      socket.on('disconnect', (reason) => {
        this.handleDisconnect(socket, reason);
      });
    });

    this.persistence.start();
    logger.info('collaboration_manager_started');
  }

  async stop(): Promise<void> {
    await this.persistence.stop();
    this.deps.logger.info('collaboration_manager_stopped');
  }

  private registerSocketHandlers(socket: Socket): void {
    socket.on('join-document', (data, ack) => this.handleJoinDocument(socket, data, ack));
    socket.on('leave-document', (data) => this.handleLeaveDocument(socket, data));
    socket.on('document-update', (data) => this.handleDocumentUpdate(socket, data));
    socket.on('cursor-update', (data) => this.handleCursorUpdate(socket, data));
    socket.on('typing-indicator', (data) => this.handleTypingIndicator(socket, data));
    socket.on('comment-add', (data) => this.comments.handleAdd(socket, data));
    socket.on('comment-update', (data) => this.comments.handleUpdate(socket, data));
    socket.on('comment-delete', (data) => this.comments.handleDelete(socket, data));
    socket.on('request-snapshot', (data) =>
      this.snapshots.handleRequestSnapshot(socket, data),
    );
    socket.on('request-history', (data) =>
      this.snapshots.handleRequestHistory(socket, data),
    );
  }

  private async handleJoinDocument(
    socket: Socket,
    data: { documentId: string },
    ack?: (response: { success: boolean; error?: string }) => void,
  ): Promise<void> {
    const { documentId } = data;
    const { io, awareness, presenceHandler, metrics, logger } = this.deps;
    const user = extractUserFromSocket(socket);
    const room = `doc:${documentId}`;

    try {
      // If socket is already in another document, leave it first
      const oldDocId = awareness.getUserDocument(socket.id);
      if (oldDocId && oldDocId !== documentId) {
        const oldRoom = `doc:${oldDocId}`;
        socket.leave(oldRoom);
        awareness.removeUser(socket.id);
        socket.to(oldRoom).emit('user-left', {
          socketId: socket.id,
          userId: user.userId,
        });
        presenceHandler.broadcastPresenceUpdate(io, oldDocId);
        if (awareness.getDocumentUserCount(oldDocId) === 0) {
          this.persistAndCleanupDocument(oldDocId);
        }
        logger.info(
          { oldDocumentId: oldDocId, newDocumentId: documentId, socketId: socket.id },
          'user_switched_documents',
        );
      }

      await socket.join(room);
      logger.info(
        { documentId, userId: user.userId, socketId: socket.id },
        'user_joined_document',
      );

      // Get or create Yjs document (safe against concurrent joins)
      const doc = await this.registry.getOrCreate(documentId);

      // Register awareness
      const userAwareness = awareness.addUser(
        documentId,
        socket.id,
        user.userId,
        user.displayName,
        user.email,
      );

      // Sync document state to joining client
      const syncStart = Date.now();
      const state = Y.encodeStateAsUpdate(doc);
      socket.emit('sync-document', {
        documentId,
        state: Buffer.from(state).toString('base64'),
      });
      metrics.documentSyncDuration.observe((Date.now() - syncStart) / 1000);

      // Notify others
      socket.to(room).emit('user-joined', {
        userId: user.userId,
        displayName: user.displayName,
        color: userAwareness.color,
        socketId: socket.id,
      });

      // Send current presence to joining user
      presenceHandler.broadcastPresenceUpdate(io, documentId);
      metrics.messagesTotal.inc({ type: 'join-document' });

      if (ack) ack({ success: true });
    } catch (err) {
      logger.error({ err, documentId, socketId: socket.id }, 'join_document_failed');
      socket.leave(room);
      metrics.connectionErrors.inc({ reason: 'join_failed' });
      if (ack) ack({ success: false, error: 'Failed to join document' });
    }
  }

  private handleLeaveDocument(socket: Socket, data: { documentId: string }): void {
    const { io, awareness, presenceHandler, metrics, logger } = this.deps;

    const mapping = awareness.removeUser(socket.id);
    // Use the document the awareness service actually tracked, falling back to client-provided id
    const trackedDocId = mapping?.documentId ?? data.documentId;
    const room = `doc:${trackedDocId}`;

    socket.leave(room);

    if (mapping) {
      socket.to(room).emit('user-left', { socketId: socket.id, userId: mapping.userId });
      presenceHandler.broadcastPresenceUpdate(io, trackedDocId);
    }
    metrics.messagesTotal.inc({ type: 'leave-document' });

    // Clean up empty documents from memory
    const userCount = awareness.getDocumentUserCount(trackedDocId);
    if (userCount === 0) {
      this.persistAndCleanupDocument(trackedDocId);
    }

    logger.info({ documentId: trackedDocId, socketId: socket.id }, 'user_left_document');
  }

  private async handleDocumentUpdate(
    socket: Socket,
    data: { documentId: string; update: unknown },
  ): Promise<void> {
    const { metrics, logger } = this.deps;
    const { documentId, update } = data;
    const room = `doc:${documentId}`;
    const user = extractUserFromSocket(socket);

    const doc = this.registry.get(documentId);
    if (!doc) {
      logger.warn({ documentId, socketId: socket.id }, 'document_update_for_unknown_doc');
      return;
    }

    // Accept legacy JSON patches for API-flow clients while preserving Yjs updates for real editors.
    if (typeof update === 'string') {
      try {
        const updateBytes = Buffer.from(update, 'base64');
        Y.applyUpdate(doc, new Uint8Array(updateBytes));
      } catch (err) {
        logger.error({ err, documentId, socketId: socket.id }, 'crdt_apply_failed');
        socket.emit('document-update-error', {
          documentId,
          error: 'Failed to apply update',
        });
        return;
      }
    }

    // Refresh the user's lastActive so active editors aren't evicted as stale
    this.deps.awareness.refreshActivity(socket.id);

    // Step 2: Broadcast to other clients immediately after successful CRDT apply
    socket.to(room).emit('document-update', { documentId, update });
    metrics.documentUpdatesTotal.inc();
    metrics.messagesTotal.inc({ type: 'document-update' });

    // Step 3: Persist to Redis as best-effort (periodic loop provides eventual consistency)
    await this.persistence.persistUpdate(documentId, doc, user.userId, socket.id);
  }

  private handleCursorUpdate(
    socket: Socket,
    data: {
      documentId: string;
      cursor: CursorPosition | null;
      selection: CursorPosition | null;
    },
  ): void {
    const { awareness, metrics } = this.deps;
    const updatedAwareness = awareness.updateCursor(
      socket.id,
      data.cursor,
      data.selection,
    );

    if (updatedAwareness) {
      const room = `doc:${data.documentId}`;
      socket.to(room).emit('cursor-update', {
        socketId: socket.id,
        userId: updatedAwareness.userId,
        displayName: updatedAwareness.displayName,
        color: updatedAwareness.color,
        cursor: data.cursor,
        selection: data.selection,
      });
      metrics.presenceUpdatesTotal.inc();
    }
  }

  private handleTypingIndicator(
    socket: Socket,
    data: { documentId: string; isTyping: boolean },
  ): void {
    const { awareness } = this.deps;
    const updated = awareness.setTyping(socket.id, data.isTyping);

    if (updated) {
      const room = `doc:${data.documentId}`;
      socket.to(room).emit('typing-indicator', {
        socketId: socket.id,
        userId: updated.userId,
        displayName: updated.displayName,
        isTyping: data.isTyping,
      });
    }
  }

  private handleDisconnect(socket: Socket, reason: string): void {
    const { io, awareness, presenceHandler, metrics, logger } = this.deps;

    metrics.activeConnections.dec();
    logger.info({ socketId: socket.id, reason }, 'client_disconnected');

    const mapping = awareness.removeUser(socket.id);
    if (mapping) {
      const room = `doc:${mapping.documentId}`;
      socket.to(room).emit('user-left', {
        socketId: socket.id,
        userId: mapping.userId,
      });
      presenceHandler.broadcastPresenceUpdate(io, mapping.documentId);

      // Clean up empty documents
      const userCount = awareness.getDocumentUserCount(mapping.documentId);
      if (userCount === 0) {
        this.persistAndCleanupDocument(mapping.documentId);
      }
    }
  }

  persistAndCleanupDocument(documentId: string): Promise<void> {
    return this.persistence.persistAndCleanupDocument(documentId);
  }
}

/** Convenience function matching the original API for backward compatibility */
export function setupCollaborationHandlers(
  io: SocketIOServer,
  documentStore: DocumentStore,
  awareness: AwarenessService,
  presenceHandler: PresenceHandler,
  metrics: MetricsCollector,
  logger: Logger,
  persistIntervalMs = 30000,
  snapshotIntervalMs = 300000,
): CollaborationManager {
  const manager = new CollaborationManager({
    io,
    documentStore,
    awareness,
    presenceHandler,
    metrics,
    logger,
    persistIntervalMs,
    snapshotIntervalMs,
  });
  manager.start();
  return manager;
}
