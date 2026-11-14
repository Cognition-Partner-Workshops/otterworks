import { createServer, type IncomingMessage, type Server } from 'http';
import type { AddressInfo } from 'net';
import type { Socket } from 'socket.io';
import {
  HttpDocumentAccessChecker,
  documentIdFromYjsRoom,
  extractSocketToken,
  isValidDocumentId,
} from '../services/document-access';

const mockLogger = {
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  debug: jest.fn(),
} as never;

const DOC_ID = '0b9c6f0e-7a51-4b1e-9d3c-2f6a1e8b4c11';

describe('HttpDocumentAccessChecker', () => {
  let server: Server;
  let baseUrl: string;
  let respond: (req: IncomingMessage) => { status: number; delayMs?: number };
  let requests: IncomingMessage[];

  beforeAll((done) => {
    server = createServer((req, res) => {
      requests.push(req);
      const { status, delayMs = 0 } = respond(req);
      setTimeout(() => {
        res.writeHead(status, { 'Content-Type': 'application/json' });
        res.end('{}');
      }, delayMs);
    });
    server.listen(0, '127.0.0.1', () => {
      baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}/`;
      done();
    });
  });

  afterAll((done) => {
    server.closeAllConnections();
    server.close(done);
  });

  beforeEach(() => {
    requests = [];
    respond = () => ({ status: 200 });
  });

  function checker(timeoutMs = 1000) {
    return new HttpDocumentAccessChecker({ baseUrl, timeoutMs }, mockLogger);
  }

  it('allows access when document-service returns the document', async () => {
    const allowed = await checker().canAccess({
      documentId: DOC_ID,
      userId: 'user-1',
      token: 'jwt-token',
    });

    expect(allowed).toBe(true);
    expect(requests).toHaveLength(1);
    expect(requests[0].method).toBe('GET');
    expect(requests[0].url).toBe(`/api/v1/documents/${DOC_ID}`);
    expect(requests[0].headers.authorization).toBe('Bearer jwt-token');
    expect(requests[0].headers['x-user-id']).toBe('user-1');
  });

  it.each([401, 403, 404, 500, 503])(
    'denies access when document-service returns %d',
    async (status) => {
      respond = () => ({ status });

      const allowed = await checker().canAccess({
        documentId: DOC_ID,
        userId: 'user-1',
        token: 'jwt-token',
      });

      expect(allowed).toBe(false);
    },
  );

  it('denies access when document-service is too slow', async () => {
    respond = () => ({ status: 200, delayMs: 500 });

    const allowed = await checker(50).canAccess({
      documentId: DOC_ID,
      userId: 'user-1',
      token: 'jwt-token',
    });

    expect(allowed).toBe(false);
  });

  it('denies access when document-service is unreachable', async () => {
    const unreachable = new HttpDocumentAccessChecker(
      { baseUrl: 'http://127.0.0.1:1', timeoutMs: 1000 },
      mockLogger,
    );

    const allowed = await unreachable.canAccess({
      documentId: DOC_ID,
      userId: 'user-1',
      token: 'jwt-token',
    });

    expect(allowed).toBe(false);
  });

  it.each([
    ['path traversal', '../../admin/users'],
    ['query injection', `${DOC_ID}?owner_id=x`],
    ['empty id', ''],
  ])('denies %s without calling document-service', async (_label, documentId) => {
    const allowed = await checker().canAccess({
      documentId,
      userId: 'user-1',
      token: 'jwt-token',
    });

    expect(allowed).toBe(false);
    expect(requests).toHaveLength(0);
  });

  it('denies access without a token or user id', async () => {
    expect(
      await checker().canAccess({ documentId: DOC_ID, userId: 'u', token: '' }),
    ).toBe(false);
    expect(
      await checker().canAccess({ documentId: DOC_ID, userId: '', token: 't' }),
    ).toBe(false);
    expect(requests).toHaveLength(0);
  });
});

describe('documentIdFromYjsRoom', () => {
  it('extracts the document id from a y-websocket room path', () => {
    expect(documentIdFromYjsRoom(`/document-${DOC_ID}`)).toBe(DOC_ID);
  });

  it.each([
    ['/'],
    ['/some-other-room'],
    [`/${DOC_ID}`],
    ['/document-'],
    ['/document-..%2F..%2Fadmin'],
    ['/document-%E0%A4%A'],
  ])('rejects %s', (pathname) => {
    expect(documentIdFromYjsRoom(pathname)).toBeNull();
  });
});

describe('isValidDocumentId', () => {
  it('accepts UUIDs and simple ids', () => {
    expect(isValidDocumentId(DOC_ID)).toBe(true);
    expect(isValidDocumentId('doc_123')).toBe(true);
  });

  it('rejects non-strings and unsafe characters', () => {
    expect(isValidDocumentId(undefined)).toBe(false);
    expect(isValidDocumentId({ $ne: null })).toBe(false);
    expect(isValidDocumentId('a/b')).toBe(false);
    expect(isValidDocumentId('a'.repeat(129))).toBe(false);
  });
});

describe('extractSocketToken', () => {
  function socketWith(handshake: Partial<Socket['handshake']>): Socket {
    return { handshake: { auth: {}, headers: {}, ...handshake } } as unknown as Socket;
  }

  it('prefers the handshake auth token', () => {
    expect(
      extractSocketToken(
        socketWith({
          auth: { token: 'from-auth' },
          headers: { authorization: 'Bearer h' },
        }),
      ),
    ).toBe('from-auth');
  });

  it('falls back to the Authorization header', () => {
    expect(
      extractSocketToken(socketWith({ headers: { authorization: 'Bearer hdr' } })),
    ).toBe('hdr');
  });

  it('returns an empty string when no token is present', () => {
    expect(extractSocketToken(socketWith({}))).toBe('');
  });
});
