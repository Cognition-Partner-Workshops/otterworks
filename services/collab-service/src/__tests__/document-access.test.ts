import { createServer, Server } from 'http';
import { canEditDocument } from '../services/document-access';

describe('Document access verification', () => {
  let server: Server;
  const originalUrl = process.env.DOCUMENT_SERVICE_URL;

  beforeAll((done) => {
    server = createServer((request, response) => {
      if (request.headers.authorization !== 'Bearer owner-token') {
        response.writeHead(403).end();
        return;
      }
      response.setHeader('Content-Type', 'application/json');
      response.end(JSON.stringify({ owner_id: 'user-a' }));
    });
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      if (address && typeof address === 'object') {
        process.env.DOCUMENT_SERVICE_URL = `http://127.0.0.1:${address.port}`;
      }
      done();
    });
  });

  afterAll((done) => {
    if (originalUrl === undefined) delete process.env.DOCUMENT_SERVICE_URL;
    else process.env.DOCUMENT_SERVICE_URL = originalUrl;
    server.close(done);
  });

  it('allows the owner using the document API', async () => {
    await expect(canEditDocument('document-a', 'owner-token', 'user-a')).resolves.toBe(
      true,
    );
  });

  it('rejects another user and missing credentials', async () => {
    await expect(canEditDocument('document-a', 'other-token', 'user-b')).resolves.toBe(
      false,
    );
    await expect(canEditDocument('document-a', '', 'user-a')).resolves.toBe(false);
    await expect(canEditDocument('document-a', 'owner-token', 'user-b')).resolves.toBe(
      false,
    );
  });

  it('fails closed when the document API is unavailable', async () => {
    process.env.DOCUMENT_SERVICE_URL = 'http://127.0.0.1:1';
    await expect(canEditDocument('document-a', 'owner-token', 'user-a')).resolves.toBe(
      false,
    );
  });
});
