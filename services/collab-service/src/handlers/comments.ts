import type { Socket } from 'socket.io';
import { extractUserFromSocket } from '../middleware/auth';
import { MetricsCollector } from '../metrics';

export interface CommentAnnotation {
  id: string;
  documentId: string;
  threadId: string;
  content: string;
  author: { userId: string; displayName: string };
  rangeStart: number;
  rangeEnd: number;
  createdAt: string;
  parentId?: string;
}

export interface CommentAddPayload {
  documentId: string;
  comment: Omit<CommentAnnotation, 'author' | 'createdAt'>;
}

export interface CommentUpdatePayload {
  documentId: string;
  commentId: string;
  content: string;
}

export interface CommentDeletePayload {
  documentId: string;
  commentId: string;
}

export interface CommentHandlerDeps {
  metrics: MetricsCollector;
}

/** Handles comment thread events (`comment-add`, `comment-update`, `comment-delete`). */
export class CommentHandler {
  private deps: CommentHandlerDeps;

  constructor(deps: CommentHandlerDeps) {
    this.deps = deps;
  }

  handleAdd(socket: Socket, data: CommentAddPayload): void {
    const { metrics } = this.deps;
    const user = extractUserFromSocket(socket);
    const room = `doc:${data.documentId}`;

    const fullComment: CommentAnnotation = {
      ...data.comment,
      documentId: data.documentId,
      author: { userId: user.userId, displayName: user.displayName },
      createdAt: new Date().toISOString(),
    };

    socket.to(room).emit('comment-added', fullComment);
    socket.emit('comment-added', fullComment);
    metrics.commentAnnotationsTotal.inc({ action: 'add' });
    metrics.messagesTotal.inc({ type: 'comment-add' });
  }

  handleUpdate(socket: Socket, data: CommentUpdatePayload): void {
    const { metrics } = this.deps;
    const user = extractUserFromSocket(socket);
    const room = `doc:${data.documentId}`;

    const payload = {
      commentId: data.commentId,
      content: data.content,
      updatedBy: { userId: user.userId, displayName: user.displayName },
      updatedAt: new Date().toISOString(),
    };

    socket.to(room).emit('comment-updated', payload);
    metrics.commentAnnotationsTotal.inc({ action: 'update' });
    metrics.messagesTotal.inc({ type: 'comment-update' });
  }

  handleDelete(socket: Socket, data: CommentDeletePayload): void {
    const { metrics } = this.deps;
    const user = extractUserFromSocket(socket);
    const room = `doc:${data.documentId}`;

    socket.to(room).emit('comment-deleted', {
      commentId: data.commentId,
      deletedBy: user.userId,
    });
    metrics.commentAnnotationsTotal.inc({ action: 'delete' });
    metrics.messagesTotal.inc({ type: 'comment-delete' });
  }
}
