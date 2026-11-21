import { loadConfig } from '../config';
import { spawnSync } from 'child_process';
import { resolve } from 'path';

describe('loadConfig JWT_SECRET', () => {
  const originalSecret = process.env.JWT_SECRET;

  afterEach(() => {
    if (originalSecret === undefined) {
      delete process.env.JWT_SECRET;
    } else {
      process.env.JWT_SECRET = originalSecret;
    }
  });

  it('refuses to start when JWT_SECRET is missing', () => {
    delete process.env.JWT_SECRET;

    expect(() => loadConfig()).toThrow('JWT_SECRET must be set and not blank');
  });

  it.each(['', ' ', '\t\n'])('rejects blank JWT_SECRET %p', (secret) => {
    process.env.JWT_SECRET = secret;

    expect(() => loadConfig()).toThrow('JWT_SECRET must be set and not blank');
  });

  it('preserves the configured secret verbatim', () => {
    const secret = '  unit-test-only-signing-key-at-least-32-bytes  ';
    process.env.JWT_SECRET = secret;

    expect(loadConfig().jwt.secret).toBe(secret);
  });

  it.each([undefined, ''])(
    'exits before serving without a usable JWT_SECRET %p',
    (secret) => {
      const env = { ...process.env };
      if (secret === undefined) {
        delete env.JWT_SECRET;
      } else {
        env.JWT_SECRET = secret;
      }

      const result = spawnSync(
        process.execPath,
        ['--require', require.resolve('tsx/cjs'), 'src/index.ts'],
        {
          cwd: resolve(__dirname, '../..'),
          env,
          encoding: 'utf8',
          timeout: 15000,
        },
      );

      expect(result.error).toBeUndefined();
      expect(result.status).toBe(1);
      expect(result.stderr).toContain('JWT_SECRET must be set and not blank');
    },
  );
});
