import type { Socket } from 'socket.io';
import { extractUserFromSocket } from '../middleware/auth';

export async function canEditDocument(
  documentId: string,
  token: string,
  userId: string,
): Promise<boolean> {
  if (!token || !userId || !documentId) return false;
  try {
    const base = process.env.DOCUMENT_SERVICE_URL || 'http://document-service:8083';
    const response = await fetch(
      `${base}/api/v1/documents/${encodeURIComponent(documentId)}`,
      {
        headers: { Authorization: `Bearer ${token}`, 'X-User-ID': userId },
        redirect: 'error',
        signal: AbortSignal.timeout(5000),
      },
    );
    if (!response.ok) return false;
    const document = (await response.json()) as { owner_id?: string };
    return document.owner_id === userId;
  } catch {
    return false;
  }
}

export async function authorizeDocument(
  socket: Socket,
  documentId: string,
): Promise<boolean> {
  const token =
    socket.handshake.auth?.token ||
    socket.handshake.headers.authorization?.replace('Bearer ', '') ||
    '';
  return canEditDocument(documentId, token, extractUserFromSocket(socket).userId);
}
