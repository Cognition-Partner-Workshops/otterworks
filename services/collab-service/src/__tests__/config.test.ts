import jwt from 'jsonwebtoken';
import { KNOWN_DEFAULT_JWT_SECRETS, loadConfig, requireJwtSecret } from '../config';
import { createAuthMiddleware } from '../middleware/auth';

const VALID_SECRET = 'a-randomly-generated-deployment-secret-0123456789';

describe('JWT secret configuration', () => {
  const originalSecret = process.env.JWT_SECRET;

  afterEach(() => {
    if (originalSecret === undefined) {
      delete process.env.JWT_SECRET;
    } else {
      process.env.JWT_SECRET = originalSecret;
    }
  });

  it('refuses to load when JWT_SECRET is unset', () => {
    delete process.env.JWT_SECRET;
    expect(() => loadConfig()).toThrow('JWT_SECRET environment variable is required');
  });

  it.each(['', '   '])('refuses to load when JWT_SECRET is blank (%p)', (secret) => {
    process.env.JWT_SECRET = secret;
    expect(() => loadConfig()).toThrow('JWT_SECRET environment variable is required');
  });

  it.each([...KNOWN_DEFAULT_JWT_SECRETS])(
    'rejects the known default secret %p',
    (secret) => {
      expect(() => requireJwtSecret(secret)).toThrow('publicly known default');
    },
  );

  it('uses the configured secret', () => {
    process.env.JWT_SECRET = VALID_SECRET;
    expect(loadConfig().jwt.secret).toBe(VALID_SECRET);
  });

  it('rejects a token forged with the former fallback secret', () => {
    process.env.JWT_SECRET = VALID_SECRET;
    const config = loadConfig();
    const logger = { warn: jest.fn(), debug: jest.fn() } as never;
    const middleware = createAuthMiddleware(config.jwt.secret, logger);
    const forged = jwt.sign({ sub: 'attacker' }, 'otterworks-dev-secret'); // nosemgrep: javascript.jsonwebtoken.security.jwt-hardcode.hardcoded-jwt-secret
    const legit = jwt.sign({ sub: 'user-1' }, VALID_SECRET); // nosemgrep: javascript.jsonwebtoken.security.jwt-hardcode.hardcoded-jwt-secret

    const forgedNext = jest.fn();
    middleware(
      { id: 's1', handshake: { auth: { token: forged }, headers: {} } } as never,
      forgedNext,
    );
    expect(forgedNext).toHaveBeenCalledWith(expect.any(Error));

    const legitNext = jest.fn();
    const socket = { id: 's2', handshake: { auth: { token: legit }, headers: {} } };
    middleware(socket as never, legitNext);
    expect(legitNext).toHaveBeenCalledWith();
    expect((socket as { user?: { userId: string } }).user?.userId).toBe('user-1');
  });
});
