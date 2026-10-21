import type { Socket } from 'socket.io';
import type { Logger } from 'pino';
import * as Y from 'yjs';
import { DocumentStore } from '../services/document-store';
import { DocRegistry } from '../services/doc-registry';
import { extractUserFromSocket } from '../middleware/auth';

export interface SnapshotRequestPayload {
  documentId: string;
  label?: string;
}

export interface HistoryRequestPayload {
  documentId: string;
  limit?: number;
}

export interface SnapshotHandlerDeps {
  registry: DocRegistry;
  documentStore: DocumentStore;
  logger: Logger;
}

/** Handles client-initiated version history events (`request-snapshot`, `request-history`). */
export class SnapshotHandler {
  private deps: SnapshotHandlerDeps;

  constructor(deps: SnapshotHandlerDeps) {
    this.deps = deps;
  }

  async handleRequestSnapshot(
    socket: Socket,
    data: SnapshotRequestPayload,
  ): Promise<void> {
    const { registry, documentStore, logger } = this.deps;
    const user = extractUserFromSocket(socket);
    const { documentId, label } = data;

    const doc = registry.get(documentId);
    if (!doc) {
      socket.emit('snapshot-error', {
        documentId,
        error: 'Document not found',
      });
      return;
    }

    try {
      const state = Y.encodeStateAsUpdate(doc);
      const snapshot = await documentStore.createSnapshot(
        documentId,
        Buffer.from(state),
        user.userId,
        label,
      );
      socket.emit('snapshot-created', snapshot);

      const room = `doc:${documentId}`;
      socket.to(room).emit('snapshot-created', snapshot);
    } catch (err) {
      logger.error({ err, documentId }, 'create_snapshot_failed');
      socket.emit('snapshot-error', {
        documentId,
        error: 'Failed to create snapshot',
      });
    }
  }

  async handleRequestHistory(socket: Socket, data: HistoryRequestPayload): Promise<void> {
    const { documentStore, logger } = this.deps;
    const { documentId, limit } = data;

    try {
      const snapshots = await documentStore.getSnapshots(documentId, limit || 20);
      socket.emit('document-history', { documentId, snapshots });
    } catch (err) {
      logger.error({ err, documentId }, 'get_history_failed');
      socket.emit('history-error', {
        documentId,
        error: 'Failed to retrieve history',
      });
    }
  }
}
