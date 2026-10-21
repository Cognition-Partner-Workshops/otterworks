import * as vitest from 'vitest';

// zone.js's vitest patch (fakeAsync/ProxyZone support) looks for a global `vitest` object and
// marks it as patched, so hand it an extensible copy of the (frozen) module namespace.
// The patch itself is loaded by test-setup-zone.ts, which runs after this file.
Object.assign(globalThis, { vitest: { ...vitest } });
