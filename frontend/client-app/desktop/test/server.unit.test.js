/* Unit tests for the embedded static + /api/v1 proxy server (src/server.ts).
 * Uses node:test against the compiled build/server.js and a throwaway web root,
 * so it runs without the client-app web build or a live API gateway.
 * Run: npm run test:unit */
const { test, describe, before, after } = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const net = require("node:net");
const os = require("node:os");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { startAppServer } = require("../build/server");

const INDEX_HTML = '<!doctype html><html><body><div id="root"></div></body></html>';

function makeWebRoot() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "otter-desktop-web-"));
  fs.writeFileSync(path.join(root, "index.html"), INDEX_HTML);
  fs.mkdirSync(path.join(root, "assets"));
  fs.writeFileSync(path.join(root, "assets", "app-abc123.js"), "console.log('app');");
  fs.writeFileSync(path.join(root, "assets", "app-abc123.css"), "body{}");
  fs.writeFileSync(path.join(root, "logo.svg"), "<svg/>");
  fs.writeFileSync(path.join(root, "favicon.ico"), "ico");
  fs.writeFileSync(path.join(root, "unknown.xyz"), "bin");
  fs.mkdirSync(path.join(root, "docs"));
  fs.writeFileSync(path.join(root, "docs", "index.html"), "<p>docs index</p>");
  return root;
}

function request(url, { method = "GET", headers = {}, body } = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request(url, { method, headers }, (res) => {
      let data = "";
      res.on("data", (c) => (data += c));
      res.on("end", () => resolve({ status: res.statusCode, headers: res.headers, body: data }));
    });
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

// Raw request so we can send paths that http.request would normalise.
function rawGet(port, rawPath) {
  return new Promise((resolve, reject) => {
    const sock = net.connect(port, "127.0.0.1", () => {
      sock.write(`GET ${rawPath} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n`);
    });
    let data = "";
    sock.on("data", (c) => (data += c));
    sock.on("end", () => resolve({ status: Number(data.split(" ")[1]), raw: data }));
    sock.on("error", reject);
  });
}

function wsUpgrade(url, timeoutMs = 2000) {
  return new Promise((resolve) => {
    const req = http.request(url, {
      headers: {
        Connection: "Upgrade",
        Upgrade: "websocket",
        "Sec-WebSocket-Key": crypto.randomBytes(16).toString("base64"),
        "Sec-WebSocket-Version": "13",
      },
    });
    const timer = setTimeout(() => {
      req.destroy();
      resolve({ outcome: "timeout" });
    }, timeoutMs);
    req.on("upgrade", (res, socket) => {
      clearTimeout(timer);
      socket.destroy();
      resolve({ outcome: "upgrade", status: res.statusCode });
    });
    req.on("response", (res) => {
      clearTimeout(timer);
      res.resume();
      resolve({ outcome: "response", status: res.statusCode });
    });
    req.on("error", (err) => {
      clearTimeout(timer);
      resolve({ outcome: "error", code: err.code });
    });
    req.end();
  });
}

describe("embedded desktop server", () => {
  let webRoot;
  let gateway;
  let gatewayHits;
  let app;

  before(async () => {
    webRoot = makeWebRoot();
    gatewayHits = [];
    gateway = http.createServer((req, res) => {
      let body = "";
      req.on("data", (c) => (body += c));
      req.on("end", () => {
        gatewayHits.push({ method: req.method, url: req.url, headers: req.headers, body });
        if (req.url.startsWith("/api/v1/polluted")) {
          res.setHeader("X-Upstream", "ok");
          res.writeHead(201, { "Content-Type": "application/json" });
          res.end("{}");
          return;
        }
        if (req.url.startsWith("/api/v1/status/")) {
          const code = Number(req.url.split("/").pop());
          res.writeHead(code, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ code }));
          return;
        }
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ method: req.method, url: req.url, body }));
      });
    });
    // Gateway that rejects WebSocket upgrades with a plain HTTP 401 (like an auth failure).
    gateway.on("upgrade", (req, socket) => {
      socket.end("HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");
    });
    await new Promise((r) => gateway.listen(0, "127.0.0.1", r));
    app = await startAppServer({
      webRoot,
      gatewayUrl: `http://127.0.0.1:${gateway.address().port}`,
      port: 0,
    });
  });

  after(async () => {
    await app.close();
    gateway.close();
    fs.rmSync(webRoot, { recursive: true, force: true });
  });

  describe("static serving", () => {
    test("binds to loopback only", () => {
      assert.match(app.url, /^http:\/\/127\.0\.0\.1:\d+$/);
      assert.equal(app.server.address().address, "127.0.0.1");
    });

    test("serves index.html at /", async () => {
      const res = await request(`${app.url}/`);
      assert.equal(res.status, 200);
      assert.equal(res.headers["content-type"], "text/html; charset=utf-8");
      assert.equal(res.body, INDEX_HTML);
      assert.equal(res.headers["cache-control"], undefined);
    });

    test("SPA fallback for deep client routes", async () => {
      for (const route of ["/dashboard", "/files", "/documents/123", "/login?next=/files"]) {
        const res = await request(`${app.url}${route}`);
        assert.equal(res.status, 200, route);
        assert.equal(res.body, INDEX_HTML, route);
      }
    });

    test("directory requests resolve to their index.html", async () => {
      const res = await request(`${app.url}/docs/`);
      assert.equal(res.status, 200);
      assert.equal(res.body, "<p>docs index</p>");
    });

    test("hashed assets get immutable caching and correct MIME types", async () => {
      const js = await request(`${app.url}/assets/app-abc123.js`);
      assert.equal(js.status, 200);
      assert.equal(js.headers["content-type"], "text/javascript; charset=utf-8");
      assert.equal(js.headers["cache-control"], "public, max-age=31536000, immutable");
      const css = await request(`${app.url}/assets/app-abc123.css`);
      assert.equal(css.headers["content-type"], "text/css; charset=utf-8");
    });

    test("MIME table covers svg/ico and falls back to octet-stream", async () => {
      assert.equal((await request(`${app.url}/logo.svg`)).headers["content-type"], "image/svg+xml");
      assert.equal((await request(`${app.url}/favicon.ico`)).headers["content-type"], "image/x-icon");
      assert.equal(
        (await request(`${app.url}/unknown.xyz`)).headers["content-type"],
        "application/octet-stream"
      );
    });

    test("sets an accurate Content-Length", async () => {
      const res = await request(`${app.url}/assets/app-abc123.js`);
      assert.equal(Number(res.headers["content-length"]), Buffer.byteLength(res.body));
    });

    test("raw ../ traversal never escapes the web root", async () => {
      const outside = path.join(path.dirname(webRoot), "otter-secret.txt");
      fs.writeFileSync(outside, "TOP SECRET");
      try {
        for (const p of [
          "/../otter-secret.txt",
          "/..%2fotter-secret.txt",
          "/%2e%2e/otter-secret.txt",
          "/assets/..%2f..%2fotter-secret.txt",
        ]) {
          const res = await rawGet(app.server.address().port, p);
          assert.ok(!res.raw.includes("TOP SECRET"), `${p} leaked a file outside webRoot`);
          assert.ok([200, 403].includes(res.status), `${p} -> ${res.status}`);
        }
      } finally {
        fs.rmSync(outside, { force: true });
      }
    });

    // [REAL] DESKTOP-01: server.ts claims parity with nginx/default.conf.template, but nginx
    // returns 404 for a missing /assets/* file (no try_files in that location), while the
    // embedded server falls back to index.html and still stamps it `immutable`, so a stale
    // chunk URL caches HTML-as-JS for a year in the Electron session cache.
    test(
      "missing hashed asset is a 404, not index.html cached as immutable",
      { todo: "[REAL] DESKTOP-01 missing /assets/* returns index.html with immutable cache" },
      async () => {
        const res = await request(`${app.url}/assets/app-deadbeef.js`);
        assert.equal(res.status, 404);
      }
    );

    // [REAL] DESKTOP-02: decodeURIComponent() throws on a malformed escape and the
    // rejection is surfaced as a 500 echoing the exception message.
    test(
      "malformed percent-encoding is a 400, not a 500",
      { todo: "[REAL] DESKTOP-02 malformed URI escape returns 500 Internal error" },
      async () => {
        const res = await rawGet(app.server.address().port, "/%E0%A4%A");
        assert.equal(res.status, 400);
      }
    );

    test("malformed percent-encoding does not crash the server", async () => {
      const res = await rawGet(app.server.address().port, "/%E0%A4%A");
      assert.ok(res.status >= 400);
      const ok = await request(`${app.url}/`);
      assert.equal(ok.status, 200);
    });
  });

  describe("/api/v1 proxy", () => {
    test("only /api/v1 and /api/v1/* are proxied", async () => {
      gatewayHits.length = 0;
      await request(`${app.url}/api/v1/files?folder=1`);
      await request(`${app.url}/api/v1`);
      await request(`${app.url}/api/v1?x=1`);
      const lookalikes = ["/api/v1x", "/api/v2/files", "/api", "/apiv1/files"];
      for (const p of lookalikes) {
        const res = await request(`${app.url}${p}`);
        assert.equal(res.body, INDEX_HTML, `${p} should be served as SPA, not proxied`);
      }
      assert.deepEqual(
        gatewayHits.map((h) => h.url),
        ["/api/v1/files?folder=1", "/api/v1", "/api/v1?x=1"]
      );
    });

    test("forwards method, body, auth header and rewrites Host", async () => {
      gatewayHits.length = 0;
      const payload = JSON.stringify({ email: "otter@example.test", password: "x" });
      const res = await request(`${app.url}/api/v1/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer unit-test-token",
          "Content-Length": Buffer.byteLength(payload),
        },
        body: payload,
      });
      assert.equal(res.status, 200);
      const hit = gatewayHits[0];
      assert.equal(hit.method, "POST");
      assert.equal(hit.body, payload);
      assert.equal(hit.headers.authorization, "Bearer unit-test-token");
      assert.equal(hit.headers.host, `127.0.0.1:${gateway.address().port}`);
      assert.equal(hit.headers["x-forwarded-proto"], "http");
      assert.ok(hit.headers["x-forwarded-for"]);
    });

    test("supports PUT/PATCH/DELETE", async () => {
      for (const method of ["PUT", "PATCH", "DELETE"]) {
        const res = await request(`${app.url}/api/v1/documents/1`, { method });
        assert.equal(JSON.parse(res.body).method, method);
      }
    });

    test("passes upstream status codes through unchanged", async () => {
      for (const code of [201, 401, 403, 404, 500, 503]) {
        const res = await request(`${app.url}/api/v1/status/${code}`);
        assert.equal(res.status, code);
      }
    });

    test("copies upstream response headers", async () => {
      const res = await request(`${app.url}/api/v1/polluted`);
      assert.equal(res.status, 201);
      assert.equal(res.headers["x-upstream"], "ok");
    });

    test("an absolute-form request URL cannot redirect the proxy to another host", async () => {
      gatewayHits.length = 0;
      const port = app.server.address().port;
      const res = await new Promise((resolve, reject) => {
        const sock = net.connect(port, "127.0.0.1", () => {
          sock.write(
            "GET http://evil.example/api/v1/steal HTTP/1.1\r\nHost: evil.example\r\nConnection: close\r\n\r\n"
          );
        });
        let data = "";
        sock.on("data", (c) => (data += c));
        sock.on("end", () => resolve(data));
        sock.on("error", reject);
      });
      // Either it is not treated as an API path (served SPA) or it lands on the gateway.
      assert.ok(!res.includes("evil.example") || res.includes('<div id="root">'));
      for (const hit of gatewayHits) assert.ok(hit.url.startsWith("/api/v1"));
    });

    test("gateway down -> 502 JSON bad_gateway", async () => {
      const deadPort = await new Promise((resolve) => {
        const s = net.createServer().listen(0, "127.0.0.1", () => {
          const p = s.address().port;
          s.close(() => resolve(p));
        });
      });
      const offline = await startAppServer({
        webRoot,
        gatewayUrl: `http://127.0.0.1:${deadPort}`,
        port: 0,
      });
      try {
        const res = await request(`${offline.url}/api/v1/files`);
        assert.equal(res.status, 502);
        assert.equal(res.headers["content-type"], "application/json");
        assert.equal(JSON.parse(res.body).error, "bad_gateway");
        // static content still served while the gateway is offline
        const index = await request(`${offline.url}/files`);
        assert.equal(index.status, 200);
        assert.equal(index.body, INDEX_HTML);
      } finally {
        await offline.close();
      }
    });

    test("non-API WebSocket upgrades are refused", async () => {
      const res = await wsUpgrade(`${app.url}/socket`);
      assert.notEqual(res.outcome, "upgrade");
      assert.notEqual(res.outcome, "timeout");
    });

    // [REAL] DESKTOP-03: proxyUpgrade() only handles the gateway's "upgrade" event. When the
    // gateway answers the upgrade with a normal HTTP response (401/404/502...) the client
    // socket is never answered or closed, so the renderer's WebSocket hangs instead of failing.
    test(
      "a rejected upstream WebSocket upgrade is reported to the client",
      { todo: "[REAL] DESKTOP-03 rejected /api/v1 WS upgrade leaves client socket hanging" },
      async () => {
        const res = await wsUpgrade(`${app.url}/api/v1/ws`, 2000);
        assert.notEqual(res.outcome, "timeout");
      }
    );
  });

  describe("lifecycle", () => {
    test("falls back to an ephemeral port when the preferred port is taken", async () => {
      const blocker = net.createServer();
      await new Promise((r) => blocker.listen(0, "127.0.0.1", r));
      const taken = blocker.address().port;
      const warn = console.warn;
      const warnings = [];
      console.warn = (m) => warnings.push(m);
      let second;
      try {
        second = await startAppServer({ webRoot, gatewayUrl: "http://127.0.0.1:1", port: taken });
        const boundPort = Number(new URL(second.url).port);
        assert.notEqual(boundPort, taken);
        assert.ok(boundPort > 0);
        assert.ok(warnings.some((w) => String(w).includes(`port ${taken} in use`)));
      } finally {
        console.warn = warn;
        if (second) await second.close();
        blocker.close();
      }
    });

    test("binds the preferred port when it is free", async () => {
      const free = await new Promise((resolve) => {
        const s = net.createServer().listen(0, "127.0.0.1", () => {
          const p = s.address().port;
          s.close(() => resolve(p));
        });
      });
      const s = await startAppServer({ webRoot, gatewayUrl: "http://127.0.0.1:1", port: free });
      try {
        assert.equal(s.url, `http://127.0.0.1:${free}`);
      } finally {
        await s.close();
      }
    });

    test("close() stops listening", async () => {
      const s = await startAppServer({ webRoot, gatewayUrl: "http://127.0.0.1:1", port: 0 });
      const url = s.url;
      await s.close();
      await assert.rejects(request(`${url}/`));
    });
  });
});
