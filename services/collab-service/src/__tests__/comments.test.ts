import { CommentHandler, type CommentAnnotation } from '../handlers/comments';
import { MetricsCollector } from '../metrics';
import { createMockSocket, testUser } from './helpers/mock-socket';

const FIXED_NOW = '2026-01-02T03:04:05.000Z';

describe('CommentHandler', () => {
  let metrics: MetricsCollector;
  let handler: CommentHandler;

  beforeEach(() => {
    jest.useFakeTimers().setSystemTime(new Date(FIXED_NOW));
    metrics = new MetricsCollector();
    handler = new CommentHandler({ metrics });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  async function counterValue(
    name: 'commentAnnotationsTotal' | 'messagesTotal',
    labels: Record<string, string>,
  ): Promise<number> {
    const metric = await metrics[name].get();
    const match = metric.values.find((v) =>
      Object.entries(labels).every(([k, val]) => v.labels[k] === val),
    );
    return match?.value ?? 0;
  }

  describe('handleAdd', () => {
    const comment = {
      id: 'c-1',
      documentId: 'ignored-client-value',
      threadId: 't-1',
      content: 'Looks good',
      rangeStart: 3,
      rangeEnd: 9,
    };

    it('stamps author and createdAt and emits comment-added to room and sender', async () => {
      const { socket, emit, to, roomEmit } = createMockSocket(testUser);

      handler.handleAdd(socket, { documentId: 'doc-1', comment });

      const expected: CommentAnnotation = {
        ...comment,
        documentId: 'doc-1',
        author: { userId: 'user-1', displayName: 'Alice' },
        createdAt: FIXED_NOW,
      };
      expect(to).toHaveBeenCalledWith('doc:doc-1');
      expect(roomEmit).toHaveBeenCalledWith('comment-added', expected);
      expect(emit).toHaveBeenCalledWith('comment-added', expected);
      expect(await counterValue('commentAnnotationsTotal', { action: 'add' })).toBe(1);
      expect(await counterValue('messagesTotal', { type: 'comment-add' })).toBe(1);
    });

    it('ignores a client-supplied author', () => {
      const { socket, emit } = createMockSocket(testUser);
      const spoofed = { ...comment, author: { userId: 'mallory', displayName: 'M' } };

      handler.handleAdd(socket, { documentId: 'doc-1', comment: spoofed });

      expect(emit.mock.calls[0][1].author).toEqual({
        userId: 'user-1',
        displayName: 'Alice',
      });
    });

    it('falls back to an anonymous author for unauthenticated sockets', () => {
      const { socket, emit } = createMockSocket(undefined, 'sock-x');

      handler.handleAdd(socket, { documentId: 'doc-1', comment });

      expect(emit.mock.calls[0][1].author).toEqual({
        userId: 'anon-sock-x',
        displayName: 'Anonymous',
      });
    });
  });

  describe('handleUpdate', () => {
    it('broadcasts comment-updated to the room only', async () => {
      const { socket, emit, to, roomEmit } = createMockSocket(testUser);

      handler.handleUpdate(socket, {
        documentId: 'doc-1',
        commentId: 'c-1',
        content: 'Edited',
      });

      expect(to).toHaveBeenCalledWith('doc:doc-1');
      expect(roomEmit).toHaveBeenCalledWith('comment-updated', {
        commentId: 'c-1',
        content: 'Edited',
        updatedBy: { userId: 'user-1', displayName: 'Alice' },
        updatedAt: FIXED_NOW,
      });
      expect(emit).not.toHaveBeenCalled();
      expect(await counterValue('commentAnnotationsTotal', { action: 'update' })).toBe(1);
      expect(await counterValue('messagesTotal', { type: 'comment-update' })).toBe(1);
    });
  });

  describe('handleDelete', () => {
    it('broadcasts comment-deleted to the room only', async () => {
      const { socket, emit, to, roomEmit } = createMockSocket(testUser);

      handler.handleDelete(socket, { documentId: 'doc-1', commentId: 'c-1' });

      expect(to).toHaveBeenCalledWith('doc:doc-1');
      expect(roomEmit).toHaveBeenCalledWith('comment-deleted', {
        commentId: 'c-1',
        deletedBy: 'user-1',
      });
      expect(emit).not.toHaveBeenCalled();
      expect(await counterValue('commentAnnotationsTotal', { action: 'delete' })).toBe(1);
      expect(await counterValue('messagesTotal', { type: 'comment-delete' })).toBe(1);
    });
  });
});
