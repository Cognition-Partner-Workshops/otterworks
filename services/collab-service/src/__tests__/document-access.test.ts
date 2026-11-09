import {
  DocumentServiceAccessClient,
  documentIdFromRoom,
} from '../services/document-access';

const mockLogger = {
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
  debug: jest.fn(),
} as never;

describe('documentIdFromRoom', () => {
  it('strips the y-websocket room prefix', () => {
    expect(documentIdFromRoom('/document-abc-123')).toBe('abc-123');
    expect(documentIdFromRoom('/document-abc-123/extra')).toBe('abc-123');
  });

  it('accepts a bare document id and rejects an empty room', () => {
    expect(documentIdFromRoom('/abc-123')).toBe('abc-123');
    expect(documentIdFromRoom('/')).toBeNull();
    expect(documentIdFromRoom('/document-')).toBeNull();
  });
});

describe('DocumentServiceAccessClient', () => {
  const fetchMock = jest.fn();
  const client = new DocumentServiceAccessClient(
    'http://document-service:8083/',
    mockLogger,
  );

  beforeEach(() => {
    fetchMock.mockReset();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  it('forwards the caller token to the document access endpoint', async () => {
    fetchMock.mockResolvedValue({ status: 200, json: async () => ({ allowed: true }) });

    await expect(client.canAccess('doc-1', 'caller-token')).resolves.toBe(true);

    expect(fetchMock).toHaveBeenCalledWith(
      'http://document-service:8083/api/v1/documents/doc-1/access',
      expect.objectContaining({ headers: { Authorization: 'Bearer caller-token' } }),
    );
  });

  it('denies when document-service says the caller is not allowed', async () => {
    fetchMock.mockResolvedValue({ status: 200, json: async () => ({ allowed: false }) });
    await expect(client.canAccess('doc-1', 'caller-token')).resolves.toBe(false);
  });

  it('denies on a non-200 response', async () => {
    fetchMock.mockResolvedValue({ status: 401, json: async () => ({}) });
    await expect(client.canAccess('doc-1', 'caller-token')).resolves.toBe(false);
  });

  it('fails closed when document-service is unreachable', async () => {
    fetchMock.mockRejectedValue(new Error('ECONNREFUSED'));
    await expect(client.canAccess('doc-1', 'caller-token')).resolves.toBe(false);
  });
});
