import * as Y from 'yjs';
import { PersistenceScheduler } from '../services/persistence-scheduler';
import { DocRegistry } from '../services/doc-registry';
import { DocumentStore } from '../services/document-store';
import { MetricsCollector } from '../metrics';

const PERSIST_MS = 1000;
const SNAPSHOT_MS = 5000;

function docWithText(text: string): Y.Doc {
  const doc = new Y.Doc();
  doc.getText('content').insert(0, text);
  return doc;
}

function decodeText(state: Buffer): string {
  const doc = new Y.Doc();
  Y.applyUpdate(doc, new Uint8Array(state));
  return doc.getText('content').toString();
}

describe('PersistenceScheduler', () => {
  let saveDocumentState: jest.Mock;
  let createSnapshot: jest.Mock;
  let getDocumentState: jest.Mock;
  let logger: { info: jest.Mock; error: jest.Mock; debug: jest.Mock };
  let metrics: MetricsCollector;
  let registry: DocRegistry;
  let activeUsers: Set<string>;
  let scheduler: PersistenceScheduler;

  beforeEach(() => {
    jest.useFakeTimers();
    saveDocumentState = jest.fn().mockResolvedValue(undefined);
    createSnapshot = jest.fn().mockResolvedValue({ id: 'snap' });
    getDocumentState = jest.fn().mockResolvedValue(null);
    logger = { info: jest.fn(), error: jest.fn(), debug: jest.fn() };
    metrics = new MetricsCollector();
    activeUsers = new Set();

    const documentStore = {
      saveDocumentState,
      createSnapshot,
      getDocumentState,
    } as unknown as DocumentStore;
    registry = new DocRegistry({ documentStore, metrics });
    scheduler = new PersistenceScheduler({
      registry,
      documentStore,
      metrics,
      logger: logger as never,
      persistIntervalMs: PERSIST_MS,
      snapshotIntervalMs: SNAPSHOT_MS,
      hasActiveUsers: (documentId) => activeUsers.has(documentId),
    });
  });

  afterEach(async () => {
    await scheduler.stop();
    jest.useRealTimers();
  });

  async function loadDoc(documentId: string, text: string): Promise<Y.Doc> {
    getDocumentState.mockResolvedValueOnce(Y.encodeStateAsUpdate(docWithText(text)));
    return registry.getOrCreate(documentId);
  }

  async function persistenceOps(operation: string, status: string): Promise<number> {
    const metric = await metrics.persistenceOperations.get();
    const match = metric.values.find(
      (v) => v.labels.operation === operation && v.labels.status === status,
    );
    return match?.value ?? 0;
  }

  describe('periodic persistence loop', () => {
    it('saves every loaded document on each tick', async () => {
      await loadDoc('doc-a', 'alpha');
      await loadDoc('doc-b', 'beta');
      scheduler.start();

      await jest.advanceTimersByTimeAsync(PERSIST_MS - 1);
      expect(saveDocumentState).not.toHaveBeenCalled();

      await jest.advanceTimersByTimeAsync(1);
      expect(saveDocumentState).toHaveBeenCalledTimes(2);
      expect(saveDocumentState.mock.calls[0][0]).toBe('doc-a');
      expect(decodeText(saveDocumentState.mock.calls[0][1])).toBe('alpha');
      expect(saveDocumentState.mock.calls[1][0]).toBe('doc-b');
      expect(await persistenceOps('periodic_save', 'success')).toBe(2);
    });

    it('logs and counts failures without stopping other documents', async () => {
      await loadDoc('doc-a', 'alpha');
      await loadDoc('doc-b', 'beta');
      saveDocumentState.mockRejectedValueOnce(new Error('redis down'));
      scheduler.start();

      await jest.advanceTimersByTimeAsync(PERSIST_MS);

      expect(saveDocumentState).toHaveBeenCalledTimes(2);
      expect(logger.error).toHaveBeenCalledWith(
        expect.objectContaining({ documentId: 'doc-a' }),
        'periodic_persistence_failed',
      );
      expect(await persistenceOps('periodic_save', 'error')).toBe(1);
      expect(await persistenceOps('periodic_save', 'success')).toBe(1);
    });
  });

  describe('auto-snapshot loop', () => {
    it('creates a system auto-snapshot for each loaded document', async () => {
      await loadDoc('doc-a', 'alpha');
      scheduler.start();

      await jest.advanceTimersByTimeAsync(SNAPSHOT_MS);

      expect(createSnapshot).toHaveBeenCalledTimes(1);
      const [documentId, state, createdBy, label] = createSnapshot.mock.calls[0];
      expect(documentId).toBe('doc-a');
      expect(decodeText(state)).toBe('alpha');
      expect(createdBy).toBe('system');
      expect(label).toBe('auto-snapshot');
    });

    it('logs snapshot failures and continues', async () => {
      await loadDoc('doc-a', 'alpha');
      await loadDoc('doc-b', 'beta');
      createSnapshot.mockRejectedValueOnce(new Error('boom'));
      scheduler.start();

      await jest.advanceTimersByTimeAsync(SNAPSHOT_MS);

      expect(createSnapshot).toHaveBeenCalledTimes(2);
      expect(logger.error).toHaveBeenCalledWith(
        expect.objectContaining({ documentId: 'doc-a' }),
        'periodic_snapshot_failed',
      );
    });
  });

  describe('stop', () => {
    it('clears timers and flushes all documents', async () => {
      await loadDoc('doc-a', 'alpha');
      scheduler.start();

      await scheduler.stop();
      expect(saveDocumentState).toHaveBeenCalledTimes(1);
      expect(logger.info).toHaveBeenCalledWith(
        { documentId: 'doc-a' },
        'document_persisted_on_shutdown',
      );

      saveDocumentState.mockClear();
      await jest.advanceTimersByTimeAsync(SNAPSHOT_MS * 2);
      expect(saveDocumentState).not.toHaveBeenCalled();
      expect(createSnapshot).not.toHaveBeenCalled();
    });

    it('keeps flushing remaining documents when one fails', async () => {
      await loadDoc('doc-a', 'alpha');
      await loadDoc('doc-b', 'beta');
      saveDocumentState.mockRejectedValueOnce(new Error('redis down'));

      await scheduler.stop();

      expect(saveDocumentState).toHaveBeenCalledTimes(2);
      expect(logger.error).toHaveBeenCalledWith(
        expect.objectContaining({ documentId: 'doc-a' }),
        'document_persist_on_shutdown_failed',
      );
    });
  });

  describe('persistUpdate', () => {
    it('saves full state attributed to the user and records metrics', async () => {
      const doc = docWithText('edited');

      await scheduler.persistUpdate('doc-a', doc, 'user-1', 'sock-1');

      expect(saveDocumentState).toHaveBeenCalledTimes(1);
      const [documentId, state, userId] = saveDocumentState.mock.calls[0];
      expect(documentId).toBe('doc-a');
      expect(decodeText(state)).toBe('edited');
      expect(userId).toBe('user-1');
      expect(await persistenceOps('save_state', 'success')).toBe(1);
    });

    it('swallows store errors, logs them and counts the failure', async () => {
      saveDocumentState.mockRejectedValueOnce(new Error('redis down'));

      await expect(
        scheduler.persistUpdate('doc-a', docWithText('x'), 'user-1', 'sock-1'),
      ).resolves.toBeUndefined();

      expect(logger.error).toHaveBeenCalledWith(
        expect.objectContaining({ documentId: 'doc-a', socketId: 'sock-1' }),
        'document_persist_failed',
      );
      expect(await persistenceOps('save_state', 'error')).toBe(1);
    });
  });

  describe('persistAndCleanupDocument', () => {
    it('persists and evicts an idle document', async () => {
      await loadDoc('doc-a', 'alpha');

      await scheduler.persistAndCleanupDocument('doc-a');

      expect(saveDocumentState).toHaveBeenCalledTimes(1);
      expect(registry.get('doc-a')).toBeUndefined();
    });

    it('persists but keeps the document when users re-joined', async () => {
      await loadDoc('doc-a', 'alpha');
      activeUsers.add('doc-a');

      await scheduler.persistAndCleanupDocument('doc-a');

      expect(saveDocumentState).toHaveBeenCalledTimes(1);
      expect(registry.get('doc-a')).toBeDefined();
    });

    it('keeps the document in memory when persistence fails', async () => {
      await loadDoc('doc-a', 'alpha');
      saveDocumentState.mockRejectedValueOnce(new Error('redis down'));

      await scheduler.persistAndCleanupDocument('doc-a');

      expect(registry.get('doc-a')).toBeDefined();
      expect(logger.error).toHaveBeenCalledWith(
        expect.objectContaining({ documentId: 'doc-a' }),
        'document_persist_on_cleanup_failed',
      );
    });

    it('is a no-op for documents that are not loaded', async () => {
      await scheduler.persistAndCleanupDocument('missing');
      expect(saveDocumentState).not.toHaveBeenCalled();
    });

    it('ignores concurrent cleanup calls for the same document', async () => {
      await loadDoc('doc-a', 'alpha');
      let release: () => void = () => {};
      saveDocumentState.mockReturnValueOnce(
        new Promise<void>((resolve) => {
          release = resolve;
        }),
      );

      const first = scheduler.persistAndCleanupDocument('doc-a');
      const second = scheduler.persistAndCleanupDocument('doc-a');
      release();
      await Promise.all([first, second]);

      expect(saveDocumentState).toHaveBeenCalledTimes(1);
      expect(registry.get('doc-a')).toBeUndefined();
    });
  });
});
