import { createServer, type IncomingMessage, type Server } from 'http';
import type { AddressInfo } from 'net';
import { DocumentAccessChecker, isValidDocumentId } from '../services/document-access';

const mockLogger = {
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  debug: jest.fn(),
  fatal: jest.fn(),
  trace: jest.fn(),
  child: jest.fn().mockReturnThis(),
  level: 'info',
} as never;

describe('DocumentAccessChecker', () => {
  let server: Server;
  let baseUrl: string;
  let requests: IncomingMessage[];
  let statusFor: (url: string) => number;

  beforeAll((done) => {
    server = createServer((req, res) => {
      requests.push(req);
      res.writeHead(statusFor(req.url || ''), { 'Content-Type': 'application/json' });
      res.end('{}');
    });
    server.listen(0, '127.0.0.1', () => {
      baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
      done();
    });
  });

  afterAll((done) => {
    server.close(done);
  });

  beforeEach(() => {
    requests = [];
    statusFor = () => 200;
  });

  const principal = { userId: 'user-a', token: 'token-a' };

  it('allows access when document-service returns 200 and forwards the caller token', async () => {
    const checker = new DocumentAccessChecker(
      { documentServiceUrl: baseUrl },
      mockLogger,
    );

    await expect(checker.canAccess('doc-1', principal)).resolves.toBe(true);
    expect(requests).toHaveLength(1);
    expect(requests[0].method).toBe('GET');
    expect(requests[0].url).toBe('/api/v1/documents/doc-1');
    expect(requests[0].headers.authorization).toBe('Bearer token-a');
    expect(requests[0].headers['x-user-id']).toBe('user-a');
  });

  it.each([401, 403, 404, 422, 500])(
    'denies access when document-service returns %i',
    async (code) => {
      statusFor = () => code;
      const checker = new DocumentAccessChecker(
        { documentServiceUrl: baseUrl },
        mockLogger,
      );

      await expect(checker.canAccess('doc-1', principal)).resolves.toBe(false);
    },
  );

  it('denies access when document-service is unreachable', async () => {
    const checker = new DocumentAccessChecker(
      { documentServiceUrl: 'http://127.0.0.1:1', timeoutMs: 500 },
      mockLogger,
    );

    await expect(checker.canAccess('doc-1', principal)).resolves.toBe(false);
  });

  it('denies invalid ids and missing tokens without calling document-service', async () => {
    const checker = new DocumentAccessChecker(
      { documentServiceUrl: baseUrl },
      mockLogger,
    );

    await expect(checker.canAccess('../admin', principal)).resolves.toBe(false);
    await expect(
      checker.canAccess('doc-1', { userId: 'user-a', token: '' }),
    ).resolves.toBe(false);
    expect(requests).toHaveLength(0);
  });

  it('caches decisions per user and document', async () => {
    statusFor = (url) => (url.endsWith('/doc-allowed') ? 200 : 403);
    const checker = new DocumentAccessChecker(
      { documentServiceUrl: baseUrl, cacheTtlMs: 60000 },
      mockLogger,
    );

    await expect(checker.canAccess('doc-allowed', principal)).resolves.toBe(true);
    await expect(checker.canAccess('doc-allowed', principal)).resolves.toBe(true);
    await expect(checker.canAccess('doc-denied', principal)).resolves.toBe(false);
    await expect(checker.canAccess('doc-denied', principal)).resolves.toBe(false);
    expect(requests).toHaveLength(2);

    await expect(
      checker.canAccess('doc-allowed', { userId: 'user-b', token: 'token-b' }),
    ).resolves.toBe(true);
    expect(requests).toHaveLength(3);
    expect(requests[2].headers.authorization).toBe('Bearer token-b');
  });
});

describe('isValidDocumentId', () => {
  it('accepts uuids and slug ids and rejects path-like or non-string values', () => {
    expect(isValidDocumentId('3f6c1f0e-8a2b-4c1d-9e7f-0a1b2c3d4e5f')).toBe(true);
    expect(isValidDocumentId('doc_sync-test')).toBe(true);
    expect(isValidDocumentId('')).toBe(false);
    expect(isValidDocumentId('a/b')).toBe(false);
    expect(isValidDocumentId('a?b')).toBe(false);
    expect(isValidDocumentId(42)).toBe(false);
    expect(isValidDocumentId('x'.repeat(129))).toBe(false);
  });
});
