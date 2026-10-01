import * as Y from 'yjs';
import { SnapshotHandler } from '../handlers/snapshots';
import { DocRegistry } from '../services/doc-registry';
import { DocumentStore, type DocumentSnapshot } from '../services/document-store';
import { MetricsCollector } from '../metrics';
import { createMockSocket, testUser } from './helpers/mock-socket';

const snapshot: DocumentSnapshot = {
  id: 'snap-1',
  documentId: 'doc-1',
  state: 'AAA=',
  createdAt: '2026-01-01T00:00:00.000Z',
  createdBy: 'user-1',
  label: 'v1',
};

describe('SnapshotHandler', () => {
  let createSnapshot: jest.Mock;
  let getSnapshots: jest.Mock;
  let getDocumentState: jest.Mock;
  let logger: { error: jest.Mock };
  let registry: DocRegistry;
  let handler: SnapshotHandler;

  beforeEach(() => {
    createSnapshot = jest.fn().mockResolvedValue(snapshot);
    getSnapshots = jest.fn().mockResolvedValue([snapshot]);
    getDocumentState = jest.fn().mockResolvedValue(null);
    logger = { error: jest.fn() };
    const documentStore = {
      createSnapshot,
      getSnapshots,
      getDocumentState,
    } as unknown as DocumentStore;
    registry = new DocRegistry({ documentStore, metrics: new MetricsCollector() });
    handler = new SnapshotHandler({ registry, documentStore, logger: logger as never });
  });

  describe('handleRequestSnapshot', () => {
    it('emits snapshot-error when the document is not loaded', async () => {
      const { socket, emit, to } = createMockSocket(testUser);

      await handler.handleRequestSnapshot(socket, { documentId: 'doc-1' });

      expect(createSnapshot).not.toHaveBeenCalled();
      expect(to).not.toHaveBeenCalled();
      expect(emit).toHaveBeenCalledWith('snapshot-error', {
        documentId: 'doc-1',
        error: 'Document not found',
      });
    });

    it('snapshots current state and emits snapshot-created to sender and room', async () => {
      const doc = await registry.getOrCreate('doc-1');
      doc.getText('content').insert(0, 'hello');
      const { socket, emit, to, roomEmit } = createMockSocket(testUser);

      await handler.handleRequestSnapshot(socket, { documentId: 'doc-1', label: 'v1' });

      const [documentId, state, userId, label] = createSnapshot.mock.calls[0];
      const restored = new Y.Doc();
      Y.applyUpdate(restored, new Uint8Array(state));
      expect(documentId).toBe('doc-1');
      expect(restored.getText('content').toString()).toBe('hello');
      expect(userId).toBe('user-1');
      expect(label).toBe('v1');
      expect(emit).toHaveBeenCalledWith('snapshot-created', snapshot);
      expect(to).toHaveBeenCalledWith('doc:doc-1');
      expect(roomEmit).toHaveBeenCalledWith('snapshot-created', snapshot);
    });

    it('emits snapshot-error when the store fails', async () => {
      await registry.getOrCreate('doc-1');
      createSnapshot.mockRejectedValueOnce(new Error('redis down'));
      const { socket, emit, roomEmit } = createMockSocket(testUser);

      await handler.handleRequestSnapshot(socket, { documentId: 'doc-1' });

      expect(emit).toHaveBeenCalledWith('snapshot-error', {
        documentId: 'doc-1',
        error: 'Failed to create snapshot',
      });
      expect(roomEmit).not.toHaveBeenCalled();
      expect(logger.error).toHaveBeenCalledWith(
        expect.objectContaining({ documentId: 'doc-1' }),
        'create_snapshot_failed',
      );
    });
  });

  describe('handleRequestHistory', () => {
    it('emits document-history with the requested limit', async () => {
      const { socket, emit } = createMockSocket(testUser);

      await handler.handleRequestHistory(socket, { documentId: 'doc-1', limit: 5 });

      expect(getSnapshots).toHaveBeenCalledWith('doc-1', 5);
      expect(emit).toHaveBeenCalledWith('document-history', {
        documentId: 'doc-1',
        snapshots: [snapshot],
      });
    });

    it('defaults the limit to 20', async () => {
      const { socket } = createMockSocket(testUser);

      await handler.handleRequestHistory(socket, { documentId: 'doc-1' });

      expect(getSnapshots).toHaveBeenCalledWith('doc-1', 20);
    });

    it('emits history-error when the store fails', async () => {
      getSnapshots.mockRejectedValueOnce(new Error('redis down'));
      const { socket, emit } = createMockSocket(testUser);

      await handler.handleRequestHistory(socket, { documentId: 'doc-1' });

      expect(emit).toHaveBeenCalledWith('history-error', {
        documentId: 'doc-1',
        error: 'Failed to retrieve history',
      });
      expect(logger.error).toHaveBeenCalledWith(
        expect.objectContaining({ documentId: 'doc-1' }),
        'get_history_failed',
      );
    });
  });
});
