import {
  DocumentAccessError,
  HttpDocumentAccessChecker,
  permissionSatisfies,
} from '../services/document-access';

const mockLogger = {
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  debug: jest.fn(),
} as never;

const DOC = '11111111-2222-4333-8444-555555555555';
const user = { userId: 'user-1', email: 'u@test.com', displayName: 'U', roles: [] };

function jsonResponse(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('HttpDocumentAccessChecker', () => {
  const fetchMock = jest.fn<Promise<Response>, [string, RequestInit]>();
  let checker: HttpDocumentAccessChecker;

  beforeEach(() => {
    fetchMock.mockReset();
    global.fetch = fetchMock as unknown as typeof fetch;
    checker = new HttpDocumentAccessChecker(
      { baseUrl: 'http://document-service:8083/', timeoutMs: 1000 },
      mockLogger,
    );
  });

  it('forwards the caller token and grants edit to the owner', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { id: DOC, owner_id: 'user-1' }));
    const permission = await checker.checkAccess({ documentId: DOC, user, token: 'tok' });
    expect(permission).toBe('edit');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`http://document-service:8083/api/v1/documents/${DOC}`);
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok');
    expect((init.headers as Record<string, string>)['X-User-ID']).toBe('user-1');
  });

  it('honours an explicit permission in the response and falls back to view for non-owners', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { owner_id: 'someone-else', permission: 'view' }),
    );
    expect(await checker.checkAccess({ documentId: DOC, user, token: 'tok' })).toBe(
      'view',
    );
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { owner_id: 'someone-else' }));
    expect(await checker.checkAccess({ documentId: DOC, user, token: 'tok' })).toBe(
      'view',
    );
  });

  it.each([401, 403, 404, 422])(
    'denies when document-service answers %i',
    async (status) => {
      fetchMock.mockResolvedValueOnce(jsonResponse(status, { detail: 'Access denied' }));
      expect(
        await checker.checkAccess({ documentId: DOC, user, token: 'tok' }),
      ).toBeNull();
    },
  );

  it('denies a malformed document id without calling document-service', async () => {
    expect(
      await checker.checkAccess({ documentId: '../admin', user, token: 'tok' }),
    ).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('grants view through a valid share token when the caller is not the owner', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(403, { detail: 'Access denied' }))
      .mockResolvedValueOnce(jsonResponse(200, { id: DOC, owner_id: 'someone-else' }));
    const permission = await checker.checkAccess({
      documentId: DOC,
      user,
      token: 'tok',
      shareToken: 'share/1',
    });
    expect(permission).toBe('view');
    expect(fetchMock.mock.calls[1][0]).toBe(
      `http://document-service:8083/api/v1/documents/shared?document_id=${DOC}&token=share%2F1`,
    );
  });

  it('denies when the share token is rejected', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(403))
      .mockResolvedValueOnce(jsonResponse(403, { detail: 'Invalid share token' }));
    expect(
      await checker.checkAccess({
        documentId: DOC,
        user,
        token: 'tok',
        shareToken: 'bad',
      }),
    ).toBeNull();
  });

  it('fails closed with DocumentAccessError on 5xx and network errors', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(500));
    await expect(
      checker.checkAccess({ documentId: DOC, user, token: 'tok' }),
    ).rejects.toBeInstanceOf(DocumentAccessError);
    fetchMock.mockRejectedValueOnce(new Error('ECONNREFUSED'));
    await expect(
      checker.checkAccess({ documentId: DOC, user, token: 'tok' }),
    ).rejects.toBeInstanceOf(DocumentAccessError);
  });
});

describe('permissionSatisfies', () => {
  it('lets edit do everything, view only view, and nothing without a grant', () => {
    expect(permissionSatisfies('edit', 'edit')).toBe(true);
    expect(permissionSatisfies('edit', 'view')).toBe(true);
    expect(permissionSatisfies('view', 'view')).toBe(true);
    expect(permissionSatisfies('view', 'edit')).toBe(false);
    expect(permissionSatisfies(undefined, 'view')).toBe(false);
  });
});
