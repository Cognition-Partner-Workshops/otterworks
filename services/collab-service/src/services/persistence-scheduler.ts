import type { Logger } from 'pino';
import * as Y from 'yjs';
import { DocumentStore } from './document-store';
import { DocRegistry } from './doc-registry';
import { MetricsCollector } from '../metrics';

export interface PersistenceSchedulerDeps {
  registry: DocRegistry;
  documentStore: DocumentStore;
  metrics: MetricsCollector;
  logger: Logger;
  persistIntervalMs: number;
  snapshotIntervalMs: number;
  /** Whether any client is still editing the document; idle docs are evicted after cleanup. */
  hasActiveUsers: (documentId: string) => boolean;
}

/** Writes live documents back to the store: per-update, periodic, auto-snapshot, cleanup and shutdown. */
export class PersistenceScheduler {
  private deps: PersistenceSchedulerDeps;
  private cleaningUp: Set<string> = new Set();
  private persistTimer: NodeJS.Timeout | null = null;
  private snapshotTimer: NodeJS.Timeout | null = null;

  constructor(deps: PersistenceSchedulerDeps) {
    this.deps = deps;
  }

  start(): void {
    this.startPersistenceLoop();
    this.startSnapshotLoop();
  }

  /** Stops the timers and flushes every in-memory document to the store. */
  async stop(): Promise<void> {
    if (this.persistTimer) clearInterval(this.persistTimer);
    if (this.snapshotTimer) clearInterval(this.snapshotTimer);

    const { registry, documentStore, logger } = this.deps;
    for (const [documentId, doc] of registry.entries()) {
      try {
        const state = Y.encodeStateAsUpdate(doc);
        await documentStore.saveDocumentState(documentId, Buffer.from(state));
        logger.info({ documentId }, 'document_persisted_on_shutdown');
      } catch (err) {
        logger.error({ err, documentId }, 'document_persist_on_shutdown_failed');
      }
    }
  }

  /** Best-effort save after a client update; the periodic loop provides eventual consistency. */
  async persistUpdate(
    documentId: string,
    doc: Y.Doc,
    userId: string,
    socketId: string,
  ): Promise<void> {
    const { documentStore, metrics, logger } = this.deps;
    try {
      const fullState = Y.encodeStateAsUpdate(doc);
      const persistStart = Date.now();
      await documentStore.saveDocumentState(documentId, Buffer.from(fullState), userId);
      metrics.persistenceDuration.observe(
        { operation: 'save_state' },
        (Date.now() - persistStart) / 1000,
      );
      metrics.persistenceOperations.inc({
        operation: 'save_state',
        status: 'success',
      });
    } catch (err) {
      logger.error({ err, documentId, socketId }, 'document_persist_failed');
      metrics.persistenceOperations.inc({
        operation: 'save_state',
        status: 'error',
      });
    }
  }

  async persistAndCleanupDocument(documentId: string): Promise<void> {
    // Guard against concurrent cleanup calls for the same document
    if (this.cleaningUp.has(documentId)) return;
    this.cleaningUp.add(documentId);

    const { registry, documentStore, logger, hasActiveUsers } = this.deps;
    const doc = registry.get(documentId);
    if (!doc) {
      this.cleaningUp.delete(documentId);
      return;
    }

    try {
      const state = Y.encodeStateAsUpdate(doc);
      await documentStore.saveDocumentState(documentId, Buffer.from(state));
      logger.info({ documentId }, 'document_persisted_on_cleanup');
      // Re-check if users have re-joined during the async persistence
      if (!hasActiveUsers(documentId)) {
        registry.remove(documentId);
        logger.debug({ documentId }, 'document_removed_from_memory');
      }
    } catch (err) {
      logger.error({ err, documentId }, 'document_persist_on_cleanup_failed');
      // Keep document in memory so the periodic persistence loop can retry
    } finally {
      this.cleaningUp.delete(documentId);
    }
  }

  private startPersistenceLoop(): void {
    const { registry, documentStore, metrics, logger } = this.deps;

    this.persistTimer = setInterval(async () => {
      for (const [documentId, doc] of registry.entries()) {
        try {
          const state = Y.encodeStateAsUpdate(doc);
          const start = Date.now();
          await documentStore.saveDocumentState(documentId, Buffer.from(state));
          metrics.persistenceDuration.observe(
            { operation: 'periodic_save' },
            (Date.now() - start) / 1000,
          );
          metrics.persistenceOperations.inc({
            operation: 'periodic_save',
            status: 'success',
          });
        } catch (err) {
          logger.error({ err, documentId }, 'periodic_persistence_failed');
          metrics.persistenceOperations.inc({
            operation: 'periodic_save',
            status: 'error',
          });
        }
      }
    }, this.deps.persistIntervalMs);
  }

  private startSnapshotLoop(): void {
    const { registry, documentStore, logger } = this.deps;

    this.snapshotTimer = setInterval(async () => {
      for (const [documentId, doc] of registry.entries()) {
        try {
          const state = Y.encodeStateAsUpdate(doc);
          await documentStore.createSnapshot(
            documentId,
            Buffer.from(state),
            'system',
            'auto-snapshot',
          );
        } catch (err) {
          logger.error({ err, documentId }, 'periodic_snapshot_failed');
        }
      }
    }, this.deps.snapshotIntervalMs);
  }
}
