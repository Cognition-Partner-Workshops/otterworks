/* QA unit tests for the embedded static + /api/v1 proxy server (src/server.ts).
 * Run: npm run build && node --test test/unit/ */
const { test, describe, before, after } = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const net = require("node:net");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const crypto = require("node:crypto");
const { startAppServer } = require("../../build/server");

const WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

function makeWebRoot() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "otter-webroot-"));
  fs.writeFileSync(path.join(root, "index.html"), '<!doctype html><div id="root"></div>');
  fs.mkdirSync(path.join(root, "assets"));
  fs.writeFileSync(path.join(root, "assets", "app-abc123.js"), "console.log('app')");
  fs.writeFileSync(path.join(root, "assets", "app-abc123.css"), "body{}");
  fs.writeFileSync(path.join(root, "favicon.svg"), "<svg/>");
  fs.writeFileSync(path.join(root, "manifest.json"), "{}");
  fs.writeFileSync(path.join(root, "logo.png"), Buffer.from([0x89, 0x50]));
  fs.writeFileSync(path.join(root, "data.unknownext"), "x");
  fs.mkdirSync(path.join(root, "nested"));
  fs.writeFileSync(path.join(root, "nested", "index.html"), "<p>nested-index</p>");
  fs.mkdirSync(path.join(root, "emptydir"));
  return root;
}

function request(url, { method = "GET", headers = {}, body, rawPath } = {}) {
  const u = new URL(url);
  return new Promise((resolve, reject) => {
    const req = http.request(
      { host: u.hostname, port: u.port, path: rawPath ?? u.pathname + u.search, method, headers },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () =>
          resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString() })
        );
      }
    );
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

let gateway;
let gatewayLog = [];
let gwUrl;

function startGateway() {
  gateway = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const entry = { method: req.method, url: req.url, headers: req.headers, body: Buffer.concat(chunks).toString() };
      gatewayLog.push(entry);
      if (req.url.startsWith("/api/v1/status/")) {
        const code = Number(req.url.split("/").pop());
        res.writeHead(code, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ error: `status ${code}` }));
      }
      if (req.url.startsWith("/api/v1/cookie")) {
        res.writeHead(200, { "Set-Cookie": ["a=1", "b=2"], "X-Custom": "yes" });
        return res.end("ok");
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(entry));
    });
  });
  gateway.on("upgrade", (req, socket) => {
    const accept = crypto.createHash("sha1").update(req.headers["sec-websocket-key"] + WS_MAGIC).digest("base64");
    socket.write(
      "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
        `Sec-WebSocket-Accept: ${accept}\r\nX-Upstream-Path: ${req.url}\r\n\r\n`
    );
  });
  return new Promise((r) => gateway.listen(0, "127.0.0.1", () => r(`http://127.0.0.1:${gateway.address().port}`)));
}

describe("embedded app server", () => {
  let app;
  let webRoot;
  before(async () => {
    webRoot = makeWebRoot();
    gwUrl = await startGateway();
    app = await startAppServer({ webRoot, gatewayUrl: gwUrl, port: 0 });
  });
  after(async () => {
    await app.close();
    gateway.close();
    fs.rmSync(webRoot, { recursive: true, force: true });
  });

  test("binds to loopback 127.0.0.1 by default", () => {
    assert.match(app.url, /^http:\/\/127\.0\.0\.1:\d+$/);
    assert.equal(app.server.address().address, "127.0.0.1");
  });

  test("serves index.html at /", async () => {
    const r = await request(`${app.url}/`);
    assert.equal(r.status, 200);
    assert.match(r.headers["content-type"], /^text\/html/);
    assert.ok(r.body.includes('<div id="root">'));
  });

  test("sets an accurate Content-Length", async () => {
    const r = await request(`${app.url}/assets/app-abc123.js`);
    assert.equal(Number(r.headers["content-length"]), Buffer.byteLength(r.body));
  });

  for (const [file, type] of [
    ["/assets/app-abc123.js", "text/javascript"],
    ["/assets/app-abc123.css", "text/css"],
    ["/favicon.svg", "image/svg+xml"],
    ["/manifest.json", "application/json"],
    ["/logo.png", "image/png"],
    ["/data.unknownext", "application/octet-stream"],
  ]) {
    test(`MIME type for ${file} is ${type}`, async () => {
      const r = await request(`${app.url}${file}`);
      assert.equal(r.status, 200);
      assert.ok(r.headers["content-type"].startsWith(type), r.headers["content-type"]);
    });
  }

  test("hashed /assets/ files get immutable cache headers", async () => {
    const r = await request(`${app.url}/assets/app-abc123.js`);
    assert.equal(r.headers["cache-control"], "public, max-age=31536000, immutable");
  });

  test("non-asset files are not marked immutable", async () => {
    const r = await request(`${app.url}/favicon.svg`);
    assert.equal(r.headers["cache-control"], undefined);
    const idx = await request(`${app.url}/`);
    assert.equal(idx.headers["cache-control"], undefined);
  });

  for (const route of ["/dashboard", "/files", "/documents/abc-123", "/settings?tab=profile", "/billing/plans"]) {
    test(`SPA fallback serves index.html for client route ${route}`, async () => {
      const r = await request(`${app.url}${route}`);
      assert.equal(r.status, 200);
      assert.ok(r.body.includes('<div id="root">'));
      assert.match(r.headers["content-type"], /^text\/html/);
    });
  }

  test("directory with index.html serves that index", async () => {
    const r = await request(`${app.url}/nested/`);
    assert.equal(r.body, "<p>nested-index</p>");
  });

  test("directory without index.html falls back to SPA index", async () => {
    const r = await request(`${app.url}/emptydir`);
    assert.equal(r.status, 200);
    assert.ok(r.body.includes('<div id="root">'));
  });

  for (const p of ["/../../etc/passwd", "/..%2f..%2f..%2fetc%2fpasswd", "/%2e%2e/%2e%2e/etc/passwd", "/assets/..%2f..%2f..%2fetc%2fpasswd"]) {
    test(`path traversal ${p} never leaks files outside webRoot`, async () => {
      const r = await request(`${app.url}`, { rawPath: p });
      assert.ok(!r.body.includes("root:x:0:0"), "leaked /etc/passwd");
      assert.ok([200, 400, 403, 404].includes(r.status), String(r.status));
    });
  }

  // nginx/default.conf.template has no try_files under /assets/, so a missing
  // hashed asset is a 404 there. The desktop server should mirror nginx.
  test("missing /assets/ file is a 404 (nginx parity), not a cached index.html", async () => {
    const r = await request(`${app.url}/assets/does-not-exist-999.js`);
    assert.notEqual(
      r.headers["cache-control"],
      "public, max-age=31536000, immutable",
      "index.html fallback served with a 1-year immutable cache header"
    );
    assert.equal(r.status, 404);
  });

  test("malformed percent-encoding is a client error, not a 500", async () => {
    const r = await request(`${app.url}`, { rawPath: "/%E0%A4%A" });
    assert.ok(r.status >= 400 && r.status < 500, `got ${r.status}: ${r.body}`);
  });

  test("server keeps serving after a malformed request", async () => {
    await request(`${app.url}`, { rawPath: "/%E0%A4%A" });
    const r = await request(`${app.url}/`);
    assert.equal(r.status, 200);
  });

  // --- proxy ---
  for (const p of ["/api/v1", "/api/v1/", "/api/v1/files?folder=root&page=2", "/api/v1?x=1"]) {
    test(`proxies ${p} to the gateway preserving path+query`, async () => {
      const r = await request(`${app.url}${p}`);
      assert.equal(r.status, 200);
      assert.equal(JSON.parse(r.body).url, p);
    });
  }

  for (const p of ["/api/v10/files", "/api/v2/files", "/api/health", "/api", "/apiv1/x"]) {
    test(`does NOT proxy non-v1 path ${p}`, async () => {
      const before = gatewayLog.length;
      const r = await request(`${app.url}${p}`);
      assert.equal(gatewayLog.length, before, "request reached the gateway");
      assert.ok(r.body.includes('<div id="root">'));
    });
  }

  test("forwards Authorization header", async () => {
    const r = await request(`${app.url}/api/v1/me`, { headers: { Authorization: "Bearer abc" } });
    assert.equal(JSON.parse(r.body).headers.authorization, "Bearer abc");
  });

  test("rewrites Host to the gateway host and sets X-Forwarded-*", async () => {
    const r = await request(`${app.url}/api/v1/me`);
    const h = JSON.parse(r.body).headers;
    assert.equal(h.host, new URL(gwUrl).host);
    assert.equal(h["x-forwarded-proto"], "http");
    assert.equal(h["x-forwarded-for"], "127.0.0.1");
  });

  for (const method of ["POST", "PUT", "PATCH", "DELETE"]) {
    test(`proxies ${method} with request body`, async () => {
      const payload = JSON.stringify({ title: `doc-${method}` });
      const r = await request(`${app.url}/api/v1/documents`, {
        method,
        body: payload,
        headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(payload) },
      });
      const echoed = JSON.parse(r.body);
      assert.equal(echoed.method, method);
      assert.equal(echoed.body, payload);
    });
  }

  for (const code of [400, 401, 403, 404, 409, 500, 503]) {
    test(`passes upstream status ${code} through unchanged`, async () => {
      const r = await request(`${app.url}/api/v1/status/${code}`);
      assert.equal(r.status, code);
      assert.equal(JSON.parse(r.body).error, `status ${code}`);
    });
  }

  test("passes multi-value Set-Cookie and custom headers through", async () => {
    const r = await request(`${app.url}/api/v1/cookie`);
    assert.deepEqual(r.headers["set-cookie"], ["a=1", "b=2"]);
    assert.equal(r.headers["x-custom"], "yes");
  });

  test("absolute-form request URI cannot redirect the proxy to another host", async () => {
    const before = gatewayLog.length;
    const r = await request(`${app.url}`, { rawPath: "http://evil.example/api/v1/files" });
    // either proxied to the trusted gateway or served as static - never elsewhere
    if (gatewayLog.length > before) {
      assert.equal(gatewayLog.at(-1).headers.host, new URL(gwUrl).host);
    } else {
      assert.ok(r.status < 500);
    }
  });

  test("WebSocket upgrade under /api/v1 is proxied", async () => {
    const res = await new Promise((resolve) => {
      const key = crypto.randomBytes(16).toString("base64");
      const req = http.request(`${app.url}/api/v1/collab/socket?room=1`, {
        headers: { Connection: "Upgrade", Upgrade: "websocket", "Sec-WebSocket-Key": key, "Sec-WebSocket-Version": "13" },
      });
      req.on("upgrade", (r, socket) => {
        resolve({
          ok: r.headers["sec-websocket-accept"] === crypto.createHash("sha1").update(key + WS_MAGIC).digest("base64"),
          path: r.headers["x-upstream-path"],
        });
        socket.destroy();
      });
      req.on("response", () => resolve({ ok: false }));
      req.on("error", () => resolve({ ok: false }));
      req.end();
    });
    assert.ok(res.ok);
    assert.equal(res.path, "/api/v1/collab/socket?room=1");
  });

  test("WebSocket upgrade outside /api/v1 is rejected", async () => {
    const result = await new Promise((resolve) => {
      const req = http.request(`${app.url}/socket.io/?EIO=4`, {
        headers: { Connection: "Upgrade", Upgrade: "websocket", "Sec-WebSocket-Key": "x", "Sec-WebSocket-Version": "13" },
      });
      req.on("upgrade", () => resolve("upgraded"));
      req.on("response", () => resolve("response"));
      req.on("error", () => resolve("destroyed"));
      req.end();
    });
    assert.equal(result, "destroyed");
  });
});

describe("gateway unavailable (offline handling)", () => {
  let app;
  let webRoot;
  before(async () => {
    webRoot = makeWebRoot();
    const tmp = net.createServer();
    await new Promise((r) => tmp.listen(0, "127.0.0.1", r));
    const deadPort = tmp.address().port;
    await new Promise((r) => tmp.close(r));
    app = await startAppServer({ webRoot, gatewayUrl: `http://127.0.0.1:${deadPort}`, port: 0 });
  });
  after(async () => {
    await app.close();
    fs.rmSync(webRoot, { recursive: true, force: true });
  });

  test("API calls return a 502 JSON bad_gateway error", async () => {
    const r = await request(`${app.url}/api/v1/files`);
    assert.equal(r.status, 502);
    assert.match(r.headers["content-type"], /application\/json/);
    assert.equal(JSON.parse(r.body).error, "bad_gateway");
  });

  test("static SPA still loads while the gateway is down", async () => {
    const r = await request(`${app.url}/dashboard`);
    assert.equal(r.status, 200);
    assert.ok(r.body.includes('<div id="root">'));
  });

  test("WebSocket upgrade to a dead gateway closes the client socket", async () => {
    const result = await new Promise((resolve) => {
      const req = http.request(`${app.url}/api/v1/collab`, {
        headers: { Connection: "Upgrade", Upgrade: "websocket", "Sec-WebSocket-Key": "x", "Sec-WebSocket-Version": "13" },
      });
      req.on("upgrade", () => resolve("upgraded"));
      req.on("error", () => resolve("closed"));
      req.end();
    });
    assert.equal(result, "closed");
  });
});

describe("port handling and lifecycle", () => {
  test("falls back to an ephemeral port when the preferred port is busy", async () => {
    const webRoot = makeWebRoot();
    const blocker = net.createServer();
    await new Promise((r) => blocker.listen(0, "127.0.0.1", r));
    const busy = blocker.address().port;
    const app = await startAppServer({ webRoot, gatewayUrl: "http://127.0.0.1:1", port: busy });
    try {
      assert.notEqual(Number(new URL(app.url).port), busy);
      assert.equal((await request(`${app.url}/`)).status, 200);
    } finally {
      await app.close();
      blocker.close();
    }
  });

  test("uses the preferred port when it is free", async () => {
    const webRoot = makeWebRoot();
    const probe = net.createServer();
    await new Promise((r) => probe.listen(0, "127.0.0.1", r));
    const free = probe.address().port;
    await new Promise((r) => probe.close(r));
    const app = await startAppServer({ webRoot, gatewayUrl: "http://127.0.0.1:1", port: free });
    assert.equal(Number(new URL(app.url).port), free);
    await app.close();
  });

  test("rejects for non-EADDRINUSE listen errors", async () => {
    await assert.rejects(
      startAppServer({ webRoot: makeWebRoot(), gatewayUrl: "http://127.0.0.1:1", port: 0, host: "203.0.113.1" })
    );
  });

  test("close() stops accepting connections", async () => {
    const app = await startAppServer({ webRoot: makeWebRoot(), gatewayUrl: "http://127.0.0.1:1", port: 0 });
    const url = app.url;
    await app.close();
    await assert.rejects(request(`${url}/`));
  });

  test("close() also tears down proxied WebSocket connections", async () => {
    const gw = http.createServer();
    gw.on("upgrade", (req, socket) => {
      const accept = crypto.createHash("sha1").update(req.headers["sec-websocket-key"] + WS_MAGIC).digest("base64");
      socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
    });
    await new Promise((r) => gw.listen(0, "127.0.0.1", r));
    const app = await startAppServer({ webRoot: makeWebRoot(), gatewayUrl: `http://127.0.0.1:${gw.address().port}`, port: 0 });
    const socket = await new Promise((resolve, reject) => {
      const req = http.request(`${app.url}/api/v1/collab`, {
        headers: { Connection: "Upgrade", Upgrade: "websocket", "Sec-WebSocket-Key": crypto.randomBytes(16).toString("base64"), "Sec-WebSocket-Version": "13" },
      });
      req.on("upgrade", (_r, s) => resolve(s));
      req.on("error", reject);
      req.end();
    });
    const closed = new Promise((r) => socket.on("close", () => r(true)));
    await app.close();
    assert.equal(await Promise.race([closed, new Promise((r) => setTimeout(() => r(false), 2000))]), true);
    gw.close();
  });
});
