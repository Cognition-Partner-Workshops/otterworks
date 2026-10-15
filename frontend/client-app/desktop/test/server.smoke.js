/* Smoke test for the embedded static + proxy server (run via `npm test`).
 * Exercises static serving, SPA fallback, asset caching, path traversal,
 * and the /api/v1 HTTP + WebSocket proxy against a stub gateway. */
const http = require("node:http");
const net = require("node:net");
const crypto = require("node:crypto");
const path = require("node:path");
const { startAppServer } = require("../build/server");

const WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

// Dummy "API gateway": echoes path + auth header; supports a raw WS handshake.
const gatewaySeen = [];
const gateway = http.createServer((req, res) => {
  gatewaySeen.push(req.url);
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ path: req.url, auth: req.headers.authorization || null }));
});
gateway.on("upgrade", (req, socket) => {
  const accept = crypto
    .createHash("sha1")
    .update(req.headers["sec-websocket-key"] + WS_MAGIC)
    .digest("base64");
  socket.write(
    "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
      `Sec-WebSocket-Accept: ${accept}\r\n\r\n`
  );
  // Send a single unmasked text frame "hi" then keep the socket open.
  socket.write(Buffer.from([0x81, 0x02, 0x68, 0x69]));
});

function get(url, headers = {}) {
  return new Promise((resolve, reject) => {
    http.get(url, { headers }, (res) => {
      let body = "";
      res.on("data", (c) => (body += c));
      res.on("end", () => resolve({ status: res.statusCode, headers: res.headers, body }));
    }).on("error", reject);
  });
}

// Raw request line, so dot-segments and percent-encoding reach the server unnormalised.
function rawGet(baseUrl, rawPath) {
  const { hostname, port } = new URL(baseUrl);
  return new Promise((resolve, reject) => {
    const socket = net.connect(Number(port), hostname, () => {
      socket.write(`GET ${rawPath} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n`);
    });
    let data = "";
    socket.on("data", (c) => (data += c));
    socket.on("end", () => resolve({ status: Number(data.split(" ")[1]), data }));
    socket.on("error", reject);
  });
}

async function main() {
  await new Promise((r) => gateway.listen(0, "127.0.0.1", r));
  const gwPort = gateway.address().port;

  const app = await startAppServer({
    webRoot: path.resolve(__dirname, "..", "..", "dist"),
    gatewayUrl: `http://127.0.0.1:${gwPort}`,
    port: 0,
  });

  let failed = false;
  const check = (name, ok, detail) => {
    console.log(`${ok ? "PASS" : "FAIL"} ${name}${ok ? "" : ` -- ${detail}`}`);
    if (!ok) failed = true;
  };

  const index = await get(`${app.url}/`);
  check("serves index.html", index.status === 200 && index.body.includes("<div id=\"root\">"), index.body.slice(0, 120));

  const spa = await get(`${app.url}/documents/some-deep/route`);
  check("SPA fallback", spa.status === 200 && spa.body.includes("<div id=\"root\">"), spa.status);

  const assetPath = index.body.match(/\/assets\/[^"]+\.js/)[0];
  const asset = await get(`${app.url}${assetPath}`);
  check(
    "asset with immutable cache",
    asset.status === 200 &&
      asset.headers["cache-control"] === "public, max-age=31536000, immutable" &&
      asset.headers["content-type"].startsWith("text/javascript"),
    JSON.stringify({ status: asset.status, cc: asset.headers["cache-control"] })
  );

  const traversal = await get(`${app.url}/..%2f..%2fpackage.json`);
  check("path traversal falls back to SPA", traversal.status === 200 && traversal.body.includes("<div id=\"root\">"), traversal.body.slice(0, 80));

  const api = await get(`${app.url}/api/v1/documents?x=1`, { Authorization: "Bearer test-token" });
  const apiBody = JSON.parse(api.body);
  check(
    "proxies /api/v1 with headers",
    api.status === 200 && apiBody.path === "/api/v1/documents?x=1" && apiBody.auth === "Bearer test-token",
    api.body
  );

  for (const escape of [
    "/api/v1/../../metrics",
    "/api/v1/%2e%2e/%2e%2e/metrics",
    "/api/v1/%2E%2E/%2E%2E/metrics",
    "/api/v1/..%2f..%2fmetrics",
    "/api/v1/..%5c..%5cmetrics",
    "/api/v1/%2f..%2f..%2fmetrics",
  ]) {
    const before = gatewaySeen.length;
    const res = await rawGet(app.url, escape);
    check(
      `rejects ${escape} escaping /api/v1 (not forwarded)`,
      res.status === 400 && gatewaySeen.length === before,
      JSON.stringify({ status: res.status, forwarded: gatewaySeen.slice(before) })
    );
  }

  for (const [raw, forwarded] of [
    ["/api/v1/files/../documents?x=1", "/api/v1/documents?x=1"],
    ["/api/v1/%2e%2e/v1/documents", "/api/v1/documents"],
    ["/api/v1/files/my%20report.pdf", "/api/v1/files/my%20report.pdf"],
  ]) {
    const before = gatewaySeen.length;
    const res = await rawGet(app.url, raw);
    check(
      `proxies in-prefix ${raw} as ${forwarded}`,
      res.status === 200 && gatewaySeen.slice(before).join() === forwarded,
      JSON.stringify({ status: res.status, forwarded: gatewaySeen.slice(before) })
    );
  }

  for (const malformed of ["/%E0%A4%A", "/api/v1/%E0%A4%A", "/api/v1/files/%zz"]) {
    const before = gatewaySeen.length;
    const res = await rawGet(app.url, malformed);
    check(
      `malformed percent-encoding ${malformed} is 400`,
      res.status === 400 && !res.data.includes("URI malformed") && gatewaySeen.length === before,
      res.data.slice(0, 120)
    );
  }
  const afterMalformed = await get(`${app.url}/`);
  check("still serves after malformed request", afterMalformed.status === 200, afterMalformed.status);

  // WebSocket upgrade through the proxy
  const wsResult = await new Promise((resolve) => {
    const key = crypto.randomBytes(16).toString("base64");
    const req = http.request(`${app.url}/api/v1/collab`, {
      headers: {
        Connection: "Upgrade",
        Upgrade: "websocket",
        "Sec-WebSocket-Key": key,
        "Sec-WebSocket-Version": "13",
      },
    });
    req.on("upgrade", (res, socket, head) => {
      const expected = crypto.createHash("sha1").update(key + WS_MAGIC).digest("base64");
      const onFrame = (frame) => {
        resolve({
          accept: res.headers["sec-websocket-accept"] === expected,
          frame: frame[0] === 0x81 && frame.subarray(2).toString() === "hi",
        });
        socket.destroy();
      };
      // The frame may coalesce with the 101 response (head) or arrive separately
      if (head && head.length) onFrame(head);
      else socket.once("data", onFrame);
    });
    req.on("response", () => resolve({ accept: false, frame: false }));
    req.on("error", () => resolve({ accept: false, frame: false }));
    setTimeout(() => resolve({ accept: false, frame: false }), 3000);
    req.end();
  });
  check("WebSocket upgrade proxied", wsResult.accept && wsResult.frame, JSON.stringify(wsResult));

  const wsEscape = await new Promise((resolve) => {
    const before = gatewaySeen.length;
    const { hostname, port } = new URL(app.url);
    const socket = net.connect(Number(port), hostname, () => {
      socket.write(
        "GET /api/v1/../../metrics HTTP/1.1\r\nHost: localhost\r\nConnection: Upgrade\r\n" +
          "Upgrade: websocket\r\nSec-WebSocket-Key: " + crypto.randomBytes(16).toString("base64") +
          "\r\nSec-WebSocket-Version: 13\r\n\r\n"
      );
    });
    let data = "";
    socket.on("data", (c) => (data += c));
    const done = () => resolve({ upgraded: data.startsWith("HTTP/1.1 101"), forwarded: gatewaySeen.length - before });
    socket.on("close", done);
    socket.on("error", done);
    setTimeout(() => { socket.destroy(); done(); }, 3000);
  });
  check("WebSocket upgrade escaping /api/v1 is refused", !wsEscape.upgraded && wsEscape.forwarded === 0, JSON.stringify(wsEscape));

  await app.close();
  gateway.close();
  process.exit(failed ? 1 : 0);
}

main().catch((err) => {
  console.error("smoke test crashed:", err);
  process.exit(1);
});
