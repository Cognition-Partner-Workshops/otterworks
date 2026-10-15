/* Unit tests for the embedded static + /api/v1 proxy server (src/server.ts).
 * Run with `npm run test:unit` (builds first). Uses a throwaway fixture web root and
 * stub gateways, so no web build or running stack is required.
 *
 * Tests marked "[REAL]" in their name document genuine defects found during QA and are
 * expected to fail until the server is fixed. */
const { test, describe, before, after } = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const net = require("node:net");
const os = require("node:os");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { startAppServer } = require("../../build/server");

const WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
const INDEX_HTML = '<!doctype html><html><body><div id="root"></div></body></html>';

function makeWebRoot() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "otter-desktop-unit-"));
  const webRoot = path.join(base, "dist");
  const files = {
    "index.html": INDEX_HTML,
    "assets/app-abc123.js": "console.log('app');",
    "assets/app-abc123.css": "body{}",
    "assets/font.woff2": "woff2",
    "logo.svg": "<svg></svg>",
    "favicon.ico": "ico",
    "manifest.json": "{}",
    "image.png": "png",
    "data.bin.unknownext": "???",
    "sub/index.html": "<p>sub index</p>",
  };
  for (const [rel, body] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(webRoot, rel)), { recursive: true });
    fs.writeFileSync(path.join(webRoot, rel), body);
  }
  // Sibling directory sharing the web root's name as a prefix ("dist" -> "dist-secret")
  fs.mkdirSync(path.join(base, "dist-secret"));
  fs.writeFileSync(path.join(base, "dist-secret", "secret.txt"), "TOP-SECRET");
  fs.writeFileSync(path.join(base, "outside.txt"), "OUTSIDE-WEBROOT");
  return { base, webRoot };
}

// Stub servers are force-closed at the end so lingering keep-alive / half-open
// upstream sockets (some deliberately left open by the [REAL] cases) can't keep
// the test process alive.
const stubServers = new Set();
after(() => {
  for (const s of stubServers) {
    if (typeof s.closeAllConnections === "function") s.closeAllConnections();
    s.close();
  }
  http.globalAgent.destroy();
});

function listen(server) {
  stubServers.add(server);
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server.address().port)));
}

function request(url, { method = "GET", headers = {}, body, timeoutMs = 3000 } = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request(url, { method, headers }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () =>
        resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks) })
      );
      res.on("error", reject);
      res.on("aborted", () => reject(new Error("response aborted")));
    });
    req.setTimeout(timeoutMs, () => req.destroy(new Error(`timed out after ${timeoutMs}ms`)));
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

/** Send a raw HTTP request over TCP and collect everything until close (or timeout). */
function rawRequest(port, text, timeoutMs = 2000) {
  return new Promise((resolve) => {
    const socket = net.connect(port, "127.0.0.1", () => socket.write(text));
    let data = "";
    let done = false;
    const finish = (timedOut) => {
      if (done) return;
      done = true;
      socket.destroy();
      resolve({ data, timedOut });
    };
    socket.on("data", (d) => (data += d));
    socket.on("close", () => finish(false));
    socket.on("error", () => finish(false));
    setTimeout(() => finish(true), timeoutMs);
  });
}

function portOf(url) {
  return Number(new URL(url).port);
}

describe("static serving", () => {
  let fixture;
  let app;
  before(async () => {
    fixture = makeWebRoot();
    app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: "http://127.0.0.1:9", port: 0 });
  });
  after(async () => {
    await app.close();
    fs.rmSync(fixture.base, { recursive: true, force: true });
  });

  test("serves index.html at / with html content type and exact length", async () => {
    const res = await request(`${app.url}/`);
    assert.equal(res.status, 200);
    assert.equal(res.headers["content-type"], "text/html; charset=utf-8");
    assert.equal(Number(res.headers["content-length"]), Buffer.byteLength(INDEX_HTML));
    assert.equal(res.body.toString(), INDEX_HTML);
  });

  const mimeCases = [
    ["/assets/app-abc123.js", "text/javascript; charset=utf-8"],
    ["/assets/app-abc123.css", "text/css; charset=utf-8"],
    ["/assets/font.woff2", "font/woff2"],
    ["/logo.svg", "image/svg+xml"],
    ["/favicon.ico", "image/x-icon"],
    ["/manifest.json", "application/json; charset=utf-8"],
    ["/image.png", "image/png"],
    ["/data.bin.unknownext", "application/octet-stream"],
  ];
  for (const [url, mime] of mimeCases) {
    test(`content type for ${url} is ${mime}`, async () => {
      const res = await request(`${app.url}${url}`);
      assert.equal(res.status, 200);
      assert.equal(res.headers["content-type"], mime);
    });
  }

  test("hashed /assets/* get immutable cache headers", async () => {
    const res = await request(`${app.url}/assets/app-abc123.js`);
    assert.equal(res.headers["cache-control"], "public, max-age=31536000, immutable");
  });

  test("index.html and root files are not cached immutably", async () => {
    for (const url of ["/", "/index.html", "/logo.svg", "/documents/abc"]) {
      const res = await request(`${app.url}${url}`);
      assert.equal(res.headers["cache-control"], undefined, url);
    }
  });

  test("directory requests resolve to that directory's index.html", async () => {
    const res = await request(`${app.url}/sub/`);
    assert.equal(res.status, 200);
    assert.equal(res.body.toString(), "<p>sub index</p>");
  });

  test("SPA fallback for client routes and missing files", async () => {
    for (const url of ["/dashboard", "/documents/123/edit", "/files?folder=1", "/missing.js"]) {
      const res = await request(`${app.url}${url}`);
      assert.equal(res.status, 200, url);
      assert.equal(res.headers["content-type"], "text/html; charset=utf-8", url);
      assert.equal(res.body.toString(), INDEX_HTML, url);
    }
  });

  test("query strings are ignored when resolving static files", async () => {
    const res = await request(`${app.url}/logo.svg?v=42`);
    assert.equal(res.headers["content-type"], "image/svg+xml");
  });

  test("HEAD returns headers without a body", async () => {
    const res = await request(`${app.url}/logo.svg`, { method: "HEAD" });
    assert.equal(res.status, 200);
    assert.equal(res.body.length, 0);
  });

  const traversalCases = [
    "/../outside.txt",
    "/..%2foutside.txt",
    "/..%2f..%2f..%2fetc%2fpasswd",
    "/%2e%2e/%2e%2e/outside.txt",
    "/assets/..%2f..%2foutside.txt",
    "/..%2fdist-secret%2fsecret.txt",
    "/....//....//outside.txt",
    "/..%5coutside.txt",
  ];
  for (const url of traversalCases) {
    test(`path traversal ${url} never escapes the web root`, async () => {
      const { data } = await rawRequest(
        portOf(app.url),
        `GET ${url} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n`
      );
      assert.ok(!data.includes("OUTSIDE-WEBROOT"), data.slice(0, 200));
      assert.ok(!data.includes("TOP-SECRET"), data.slice(0, 200));
      assert.ok(!data.includes("root:x:0:0"), data.slice(0, 200));
    });
  }

  test("server keeps serving after a malformed percent-encoded path", async () => {
    await request(`${app.url}/%E0%A4%A`);
    const res = await request(`${app.url}/`);
    assert.equal(res.status, 200);
  });

  test("[REAL] malformed percent-encoding is a 400 client error, not a 500 leaking the exception", async () => {
    // nginx (the production equivalent) answers 400 Bad Request; the desktop server
    // currently replies 500 "Internal error: URI malformed".
    const res = await request(`${app.url}/%E0%A4%A`);
    assert.equal(res.status, 400);
    assert.ok(!res.body.toString().includes("URI malformed"), res.body.toString());
  });
});

describe("/api/v1 HTTP proxy", () => {
  let fixture;
  let gateway;
  let gatewayPort;
  let app;
  const seen = [];

  before(async () => {
    fixture = makeWebRoot();
    gateway = http.createServer((req, res) => {
      const chunks = [];
      req.on("data", (c) => chunks.push(c));
      req.on("end", () => {
        const body = Buffer.concat(chunks);
        seen.push({ method: req.method, url: req.url, headers: req.headers, body });
        const url = new URL(req.url, "http://x");
        if (url.pathname === "/api/v1/status") {
          const code = Number(url.searchParams.get("code"));
          const headers = { "x-upstream": "yes" };
          if (code === 401) headers["www-authenticate"] = "Bearer";
          if (code === 302) headers.location = "/api/v1/elsewhere";
          res.writeHead(code, headers);
          res.end(code === 204 || code === 304 ? undefined : JSON.stringify({ code }));
          return;
        }
        if (url.pathname === "/api/v1/cookies") {
          res.setHeader("set-cookie", ["a=1; Path=/", "b=2; Path=/"]);
          res.end("ok");
          return;
        }
        if (url.pathname === "/api/v1/hash") {
          res.end(crypto.createHash("sha256").update(body).digest("hex"));
          return;
        }
        if (url.pathname === "/api/v1/big") {
          res.writeHead(200, { "content-type": "application/octet-stream" });
          res.end(Buffer.alloc(3 * 1024 * 1024, 7));
          return;
        }
        res.writeHead(200, { "content-type": "application/json" });
        res.end(JSON.stringify({ method: req.method, url: req.url, headers: req.headers, body: body.toString() }));
      });
    });
    gatewayPort = await listen(gateway);
    app = await startAppServer({
      webRoot: fixture.webRoot,
      gatewayUrl: `http://127.0.0.1:${gatewayPort}`,
      port: 0,
    });
  });
  after(async () => {
    await app.close();
    gateway.close();
    fs.rmSync(fixture.base, { recursive: true, force: true });
  });

  for (const url of ["/api/v1", "/api/v1/", "/api/v1/documents", "/api/v1?ping=1", "/api/v1/files/abc/download?x=1&y=2"]) {
    test(`${url} is proxied to the gateway with path and query intact`, async () => {
      const res = await request(`${app.url}${url}`);
      assert.equal(res.status, 200);
      assert.equal(JSON.parse(res.body).url, url);
    });
  }

  for (const url of ["/api/v1x", "/api/v2/documents", "/api", "/api/", "/apiv1/documents"]) {
    test(`${url} is NOT proxied (served by the SPA fallback)`, async () => {
      const before = seen.length;
      const res = await request(`${app.url}${url}`);
      assert.equal(res.body.toString(), INDEX_HTML);
      assert.equal(seen.length, before, "gateway must not be contacted");
    });
  }

  test("forwards method, JSON body, Authorization and sets gateway Host + X-Forwarded-*", async () => {
    const payload = JSON.stringify({ title: "Desktop doc", content: "hello" });
    const res = await request(`${app.url}/api/v1/documents/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer abc.def", "Content-Length": Buffer.byteLength(payload) },
      body: payload,
    });
    const echoed = JSON.parse(res.body);
    assert.equal(echoed.method, "POST");
    assert.equal(echoed.body, payload);
    assert.equal(echoed.headers.authorization, "Bearer abc.def");
    assert.equal(echoed.headers.host, `127.0.0.1:${gatewayPort}`);
    assert.equal(echoed.headers["x-forwarded-proto"], "http");
    assert.equal(echoed.headers["x-forwarded-for"], "127.0.0.1");
  });

  for (const method of ["PUT", "PATCH", "DELETE", "OPTIONS"]) {
    test(`forwards ${method} requests`, async () => {
      const res = await request(`${app.url}/api/v1/files/1`, { method });
      assert.equal(JSON.parse(res.body).method, method);
    });
  }

  for (const code of [201, 204, 302, 400, 401, 403, 404, 409, 500, 503]) {
    test(`passes upstream ${code} through unchanged`, async () => {
      const res = await request(`${app.url}/api/v1/status?code=${code}`);
      assert.equal(res.status, code);
      assert.equal(res.headers["x-upstream"], "yes");
      if (code === 401) assert.equal(res.headers["www-authenticate"], "Bearer");
      if (code === 302) assert.equal(res.headers.location, "/api/v1/elsewhere");
    });
  }

  test("preserves multiple Set-Cookie headers", async () => {
    const res = await request(`${app.url}/api/v1/cookies`);
    assert.deepEqual(res.headers["set-cookie"], ["a=1; Path=/", "b=2; Path=/"]);
  });

  test("streams a 2 MiB binary upload byte-exact", async () => {
    const payload = crypto.randomBytes(2 * 1024 * 1024);
    const res = await request(`${app.url}/api/v1/hash`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream", "Content-Length": payload.length },
      body: payload,
      timeoutMs: 10000,
    });
    assert.equal(res.body.toString(), crypto.createHash("sha256").update(payload).digest("hex"));
  });

  test("streams a 3 MiB binary download byte-exact", async () => {
    const res = await request(`${app.url}/api/v1/big`, { timeoutMs: 10000 });
    assert.equal(res.body.length, 3 * 1024 * 1024);
    assert.ok(res.body.every((b) => b === 7));
  });

  test("absolute-form request URIs cannot redirect the proxy to another host", async () => {
    const before = seen.length;
    const { data } = await rawRequest(
      portOf(app.url),
      "GET http://evil.example/api/v1/steal HTTP/1.1\r\nHost: evil.example\r\nConnection: close\r\n\r\n"
    );
    assert.ok(!data.includes("evil.example"), data.slice(0, 200));
    for (const r of seen.slice(before)) assert.equal(r.headers.host, `127.0.0.1:${gatewayPort}`);
  });

  test("Host header spoofing does not change the upstream Host", async () => {
    const res = await request(`${app.url}/api/v1/whoami`, { headers: { Host: "evil.example" } });
    assert.equal(JSON.parse(res.body).headers.host, `127.0.0.1:${gatewayPort}`);
  });

  test("[REAL] dot-segments cannot escape the /api/v1 prefix to reach non-API gateway routes", async () => {
    // nginx normalises the URI before matching `location /api/v1/`, so
    // /api/v1/../../metrics is served by the SPA. The desktop server matches the raw
    // path but forwards the WHATWG-normalised one, reaching gateway-internal routes.
    for (const url of ["/api/v1/../../internal/metrics", "/api/v1/%2e%2e/%2e%2e/debug"]) {
      const before = seen.length;
      await rawRequest(portOf(app.url), `GET ${url} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n`);
      const forwarded = seen.slice(before).map((r) => r.url);
      for (const u of forwarded) assert.ok(u.startsWith("/api/v1"), `${url} was forwarded as ${u}`);
    }
  });
});

describe("prototype-pollution-safe response headers", () => {
  test("drops __proto__/constructor/prototype upstream headers and does not pollute Object.prototype", async () => {
    const fixture = makeWebRoot();
    const gw = net.createServer((socket) => {
      socket.once("data", () => {
        socket.end(
          "HTTP/1.1 200 OK\r\n__proto__: polluted\r\nconstructor: bad\r\nprototype: bad\r\n" +
            "X-Safe: ok\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"
        );
      });
    });
    const port = await listen(gw);
    const app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: `http://127.0.0.1:${port}`, port: 0 });
    try {
      const { data } = await rawRequest(portOf(app.url), "GET /api/v1/x HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n");
      assert.match(data, /x-safe: ok/i);
      assert.doesNotMatch(data, /__proto__/i);
      assert.doesNotMatch(data, /^constructor:/im);
      assert.doesNotMatch(data, /^prototype:/im);
      assert.equal({}.polluted, undefined);
    } finally {
      await app.close();
      gw.close();
      fs.rmSync(fixture.base, { recursive: true, force: true });
    }
  });
});

describe("gateway failure handling", () => {
  let fixture;
  before(() => {
    fixture = makeWebRoot();
  });
  after(() => fs.rmSync(fixture.base, { recursive: true, force: true }));

  test("gateway down -> 502 JSON bad_gateway, static app still served", async () => {
    const probe = http.createServer();
    const deadPort = await listen(probe);
    await new Promise((r) => probe.close(r));
    const app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: `http://127.0.0.1:${deadPort}`, port: 0 });
    try {
      const res = await request(`${app.url}/api/v1/auth/login`, { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } });
      assert.equal(res.status, 502);
      assert.equal(res.headers["content-type"], "application/json");
      assert.equal(JSON.parse(res.body).error, "bad_gateway");
      const page = await request(`${app.url}/login`);
      assert.equal(page.status, 200);
      assert.equal(page.body.toString(), INDEX_HTML);
    } finally {
      await app.close();
    }
  });

  test("[REAL] upstream connection reset mid-response terminates the client response instead of hanging", async () => {
    const gw = http.createServer((req, res) => {
      res.writeHead(200, { "content-type": "text/plain", "content-length": "1000" });
      res.write("partial");
      setTimeout(() => req.socket.destroy(), 50);
    });
    const port = await listen(gw);
    const app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: `http://127.0.0.1:${port}`, port: 0 });
    try {
      const outcome = await request(`${app.url}/api/v1/slow`, { timeoutMs: 2000 }).then(
        () => "completed",
        (err) => err.message
      );
      assert.notEqual(outcome, "timed out after 2000ms", "client request hung after upstream reset");
    } finally {
      await app.close();
      gw.close();
    }
  });

  test("[REAL] client aborting an upload aborts the upstream request", async () => {
    let upstreamClosed = false;
    const gw = http.createServer((req) => {
      req.on("close", () => (upstreamClosed = true));
      req.resume();
    });
    const port = await listen(gw);
    const app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: `http://127.0.0.1:${port}`, port: 0 });
    try {
      const socket = net.connect(portOf(app.url), "127.0.0.1", () => {
        socket.write("POST /api/v1/files/upload HTTP/1.1\r\nHost: x\r\nContent-Length: 100000\r\n\r\npartial");
        setTimeout(() => socket.destroy(), 200);
      });
      socket.on("error", () => {});
      await new Promise((r) => setTimeout(r, 1500));
      assert.ok(upstreamClosed, "upstream request left open after the client went away");
    } finally {
      await app.close();
      gw.close();
    }
  });
});

describe("WebSocket upgrade proxy", () => {
  let fixture;
  before(() => {
    fixture = makeWebRoot();
  });
  after(() => fs.rmSync(fixture.base, { recursive: true, force: true }));

  function wsHandshake(port, urlPath, timeoutMs = 2000) {
    const key = crypto.randomBytes(16).toString("base64");
    return rawRequest(
      port,
      `GET ${urlPath} HTTP/1.1\r\nHost: x\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n` +
        `Sec-WebSocket-Key: ${key}\r\nSec-WebSocket-Version: 13\r\n\r\n`,
      timeoutMs
    ).then((r) => ({ ...r, key }));
  }

  test("bidirectional frames flow through /api/v1/collab", async () => {
    const gw = http.createServer();
    gw.on("upgrade", (req, socket) => {
      const accept = crypto.createHash("sha1").update(req.headers["sec-websocket-key"] + WS_MAGIC).digest("base64");
      socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
      // Echo raw bytes back so the client can verify upstream received what it sent.
      socket.on("data", (d) => socket.write(d));
    });
    const port = await listen(gw);
    const app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: `http://127.0.0.1:${port}`, port: 0 });
    try {
      const echoed = await new Promise((resolve, reject) => {
        const key = crypto.randomBytes(16).toString("base64");
        const req = http.request(`${app.url}/api/v1/collab?doc=1`, {
          headers: { Connection: "Upgrade", Upgrade: "websocket", "Sec-WebSocket-Key": key, "Sec-WebSocket-Version": "13" },
        });
        req.on("upgrade", (res, socket) => {
          const expected = crypto.createHash("sha1").update(key + WS_MAGIC).digest("base64");
          assert.equal(res.headers["sec-websocket-accept"], expected);
          socket.once("data", (d) => {
            socket.destroy();
            resolve(d.toString());
          });
          socket.write("ping-from-renderer");
        });
        req.on("error", reject);
        setTimeout(() => reject(new Error("timeout")), 3000);
        req.end();
      });
      assert.equal(echoed, "ping-from-renderer");
    } finally {
      await app.close();
      gw.close();
    }
  });

  test("upgrade on a non-API path is refused (socket destroyed)", async () => {
    const app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: "http://127.0.0.1:9", port: 0 });
    try {
      const { data, timedOut } = await wsHandshake(portOf(app.url), "/socket.io/");
      assert.equal(timedOut, false);
      assert.equal(data, "");
    } finally {
      await app.close();
    }
  });

  test("upgrade with the gateway down closes the client socket", async () => {
    const probe = http.createServer();
    const deadPort = await listen(probe);
    await new Promise((r) => probe.close(r));
    const app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: `http://127.0.0.1:${deadPort}`, port: 0 });
    try {
      const { timedOut } = await wsHandshake(portOf(app.url), "/api/v1/collab");
      assert.equal(timedOut, false, "client socket left hanging");
    } finally {
      await app.close();
    }
  });

  test("[REAL] upgrade rejected by the gateway (e.g. 401) is surfaced to the client instead of hanging", async () => {
    const gw = http.createServer();
    gw.on("upgrade", (_req, socket) => socket.end("HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n"));
    const port = await listen(gw);
    const app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: `http://127.0.0.1:${port}`, port: 0 });
    try {
      const { data, timedOut } = await wsHandshake(portOf(app.url), "/api/v1/collab");
      assert.equal(timedOut, false, `client socket hung; received: ${JSON.stringify(data)}`);
    } finally {
      await app.close();
      gw.close();
    }
  });
});

describe("server lifecycle", () => {
  let fixture;
  before(() => {
    fixture = makeWebRoot();
  });
  after(() => fs.rmSync(fixture.base, { recursive: true, force: true }));

  test("binds the preferred port when free", async () => {
    const probe = http.createServer();
    const freePort = await listen(probe);
    await new Promise((r) => probe.close(r));
    const app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: "http://127.0.0.1:9", port: freePort });
    try {
      assert.equal(app.url, `http://127.0.0.1:${freePort}`);
    } finally {
      await app.close();
    }
  });

  test("falls back to an ephemeral port when the preferred port is taken", async () => {
    const blocker = http.createServer();
    const taken = await listen(blocker);
    const app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: "http://127.0.0.1:9", port: taken });
    try {
      const port = portOf(app.url);
      assert.notEqual(port, taken);
      assert.ok(port > 0);
      assert.equal((await request(`${app.url}/`)).status, 200);
    } finally {
      await app.close();
      blocker.close();
    }
  });

  test("binds loopback only by default", async () => {
    const app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: "http://127.0.0.1:9", port: 0 });
    try {
      assert.equal(app.server.address().address, "127.0.0.1");
      assert.match(app.url, /^http:\/\/127\.0\.0\.1:\d+$/);
    } finally {
      await app.close();
    }
  });

  test("rejects on non-EADDRINUSE listen errors", async () => {
    await assert.rejects(
      startAppServer({ webRoot: fixture.webRoot, gatewayUrl: "http://127.0.0.1:9", port: 0, host: "203.0.113.1" })
    );
  });

  test("close() resolves and tears down keep-alive and upgraded sockets", async () => {
    const gw = http.createServer();
    gw.on("upgrade", (req, socket) => {
      const accept = crypto.createHash("sha1").update(req.headers["sec-websocket-key"] + WS_MAGIC).digest("base64");
      socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\n\r\n`);
    });
    const gwPort = await listen(gw);
    const app = await startAppServer({ webRoot: fixture.webRoot, gatewayUrl: `http://127.0.0.1:${gwPort}`, port: 0 });
    const keepAlive = new http.Agent({ keepAlive: true });
    await new Promise((r) => http.get(`${app.url}/`, { agent: keepAlive }, (res) => res.resume().on("end", r)));
    const wsClosed = new Promise((resolve) => {
      const key = crypto.randomBytes(16).toString("base64");
      const req = http.request(`${app.url}/api/v1/collab`, {
        headers: { Connection: "Upgrade", Upgrade: "websocket", "Sec-WebSocket-Key": key, "Sec-WebSocket-Version": "13" },
      });
      req.on("upgrade", (_res, socket) => socket.on("close", () => resolve(true)));
      req.end();
    });
    await new Promise((r) => setTimeout(r, 200));
    const closed = await Promise.race([app.close().then(() => "closed"), new Promise((r) => setTimeout(() => r("hung"), 3000))]);
    assert.equal(closed, "closed");
    assert.equal(await Promise.race([wsClosed, new Promise((r) => setTimeout(() => r(false), 2000))]), true);
    keepAlive.destroy();
    gw.close();
  });
});
