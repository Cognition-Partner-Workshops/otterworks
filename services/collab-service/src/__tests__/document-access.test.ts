import {
  DocumentServiceAccessChecker,
  isValidDocumentId,
} from '../services/document-access';

const mockLogger = {
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  debug: jest.fn(),
} as never;

const DOC_ID = '3f2b8c1e-9a4d-4e2f-b6a1-0c5d7e8f9a10';

function checkerWith(fetchImpl: jest.Mock): DocumentServiceAccessChecker {
  return new DocumentServiceAccessChecker(
    { baseUrl: 'http://document-service:8083/', timeoutMs: 1000 },
    mockLogger,
    fetchImpl as unknown as typeof fetch,
  );
}

describe('DocumentServiceAccessChecker', () => {
  it('asks document-service for the document with the caller credentials', async () => {
    const fetchImpl = jest.fn().mockResolvedValue({ ok: true, status: 200 });

    await expect(checkerWith(fetchImpl).canAccess(DOC_ID, 'user-1', 'tok')).resolves.toBe(
      true,
    );

    expect(fetchImpl).toHaveBeenCalledWith(
      `http://document-service:8083/api/v1/documents/${DOC_ID}`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          Authorization: 'Bearer tok',
          'X-User-ID': 'user-1',
        }),
      }),
    );
  });

  it.each([401, 403, 404, 500])(
    'denies when document-service answers %i',
    async (status) => {
      const fetchImpl = jest.fn().mockResolvedValue({ ok: false, status });

      await expect(
        checkerWith(fetchImpl).canAccess(DOC_ID, 'user-1', 'tok'),
      ).resolves.toBe(false);
    },
  );

  it('denies when document-service is unreachable', async () => {
    const fetchImpl = jest.fn().mockRejectedValue(new Error('ECONNREFUSED'));

    await expect(checkerWith(fetchImpl).canAccess(DOC_ID, 'user-1', 'tok')).resolves.toBe(
      false,
    );
  });

  it('denies malformed ids and missing tokens without calling document-service', async () => {
    const fetchImpl = jest.fn();
    const checker = checkerWith(fetchImpl);

    await expect(checker.canAccess('../admin', 'user-1', 'tok')).resolves.toBe(false);
    await expect(checker.canAccess(DOC_ID, 'user-1', '')).resolves.toBe(false);
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});

describe('isValidDocumentId', () => {
  it('accepts UUIDs only', () => {
    expect(isValidDocumentId(DOC_ID)).toBe(true);
    expect(isValidDocumentId('doc-1')).toBe(false);
    expect(isValidDocumentId(`${DOC_ID}/versions`)).toBe(false);
    expect(isValidDocumentId(undefined)).toBe(false);
  });
});
