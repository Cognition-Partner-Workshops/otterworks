/* QA unit tests for the Electron main process (src/main.ts) with a stubbed
 * `electron` module, so window/navigation/lifecycle wiring is checked without
 * launching a real browser. Run: npm run build && node --test test/unit/ */
const { test, describe, beforeEach, afterEach } = require("node:test");
const assert = require("node:assert/strict");
const Module = require("node:module");
const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");

const MAIN = path.resolve(__dirname, "..", "..", "build", "main.js");
const SERVER = path.resolve(__dirname, "..", "..", "build", "server.js");

function makeElectronStub({ lock = true, isPackaged = false } = {}) {
  const events = {};
  const calls = { quit: 0, exit: [], openExternal: [], errorBox: [], windows: [], setAppUserModelId: [] };
  let readyResolve;
  const ready = new Promise((r) => (readyResolve = r));

  class BrowserWindow {
    constructor(opts) {
      this.opts = opts;
      this.loaded = null;
      this.minimized = false;
      this.restored = 0;
      this.focused = 0;
      this.wcEvents = {};
      this.wcOnce = {};
      const self = this;
      this.webContents = {
        setWindowOpenHandler(fn) { self.openHandler = fn; },
        on(name, fn) { self.wcEvents[name] = fn; },
        once(name, fn) { self.wcOnce[name] = fn; },
      };
      BrowserWindow.all.push(this);
      calls.windows.push(this);
    }
    loadURL(u) { this.loaded = u; }
    isMinimized() { return this.minimized; }
    restore() { this.restored++; }
    focus() { this.focused++; }
    static getAllWindows() { return BrowserWindow.all; }
  }
  BrowserWindow.all = [];

  const app = {
    isPackaged,
    requestSingleInstanceLock: () => lock,
    quit: () => { calls.quit++; },
    exit: (code) => { calls.exit.push(code); },
    on: (name, fn) => { events[name] = fn; },
    whenReady: () => ready,
    setAppUserModelId: (id) => calls.setAppUserModelId.push(id),
    dock: { setIcon() {} },
  };
  return {
    module: {
      app,
      BrowserWindow,
      dialog: { showErrorBox: (t, m) => calls.errorBox.push([t, m]) },
      shell: { openExternal: (u) => { calls.openExternal.push(u); return Promise.resolve(); } },
    },
    events,
    calls,
    fireReady: () => readyResolve(),
  };
}

const origLoad = Module._load;
let savedEnv;
let savedArgv;
let started = [];

function loadMain(stub, { serverStub } = {}) {
  delete require.cache[MAIN];
  delete require.cache[SERVER];
  Module._load = function (request, parent, isMain) {
    if (request === "electron") return stub.module;
    if (serverStub && request === "./server" && parent && parent.filename === MAIN) return serverStub;
    return origLoad.apply(this, arguments);
  };
  require(MAIN);
}

const flush = () => new Promise((r) => setTimeout(r, 30));

function fakeServer(url = "http://127.0.0.1:34117") {
  const closes = { n: 0 };
  return {
    closes,
    stub: {
      startAppServer: async (opts) => {
        started.push(opts);
        return { url, close: async () => { closes.n++; } };
      },
    },
  };
}

beforeEach(() => {
  savedEnv = { ...process.env };
  savedArgv = process.argv;
  started = [];
  delete process.env.ELECTRON_START_URL;
  delete process.env.API_GATEWAY_URL;
  delete process.env.OTTER_DESKTOP_PORT;
});
afterEach(() => {
  Module._load = origLoad;
  process.env = savedEnv;
  process.argv = savedArgv;
});

describe("window creation", () => {
  test("creates one secure 1280x800 'OtterWorks' window pointed at the embedded server", async () => {
    const stub = makeElectronStub();
    const fs1 = fakeServer();
    loadMain(stub, { serverStub: fs1.stub });
    stub.fireReady();
    await flush();
    assert.equal(stub.calls.windows.length, 1);
    const win = stub.calls.windows[0];
    assert.equal(win.opts.width, 1280);
    assert.equal(win.opts.height, 800);
    assert.equal(win.opts.title, "OtterWorks");
    assert.deepEqual(win.opts.webPreferences, { contextIsolation: true, nodeIntegration: false, sandbox: true });
    assert.equal(win.loaded, "http://127.0.0.1:34117");
  });

  test("defaults: gateway http://localhost:8080 and port 34117", async () => {
    const stub = makeElectronStub();
    loadMain(stub, { serverStub: fakeServer().stub });
    stub.fireReady();
    await flush();
    assert.equal(started.length, 1);
    assert.equal(started[0].gatewayUrl, "http://localhost:8080");
    assert.equal(started[0].port, 34117);
    assert.ok(started[0].webRoot.endsWith(path.join("client-app", "dist")), started[0].webRoot);
  });

  test("honours API_GATEWAY_URL and OTTER_DESKTOP_PORT", async () => {
    process.env.API_GATEWAY_URL = "http://gw.internal:9000";
    process.env.OTTER_DESKTOP_PORT = "45678";
    const stub = makeElectronStub();
    loadMain(stub, { serverStub: fakeServer().stub });
    stub.fireReady();
    await flush();
    assert.equal(started[0].gatewayUrl, "http://gw.internal:9000");
    assert.equal(started[0].port, 45678);
  });

  test("non-numeric OTTER_DESKTOP_PORT falls back to 34117", async () => {
    process.env.OTTER_DESKTOP_PORT = "not-a-port";
    const stub = makeElectronStub();
    loadMain(stub, { serverStub: fakeServer().stub });
    stub.fireReady();
    await flush();
    assert.equal(started[0].port, 34117);
  });

  test("ELECTRON_START_URL skips the embedded server", async () => {
    process.env.ELECTRON_START_URL = "http://localhost:3000";
    const stub = makeElectronStub();
    loadMain(stub, { serverStub: fakeServer().stub });
    stub.fireReady();
    await flush();
    assert.equal(started.length, 0);
    assert.equal(stub.calls.windows[0].loaded, "http://localhost:3000");
  });

  test("missing web build shows an error dialog and exits 1", async () => {
    const stub = makeElectronStub({ isPackaged: true });
    const empty = fs.mkdtempSync(path.join(os.tmpdir(), "otter-res-"));
    const origRes = process.resourcesPath;
    Object.defineProperty(process, "resourcesPath", { value: empty, configurable: true, writable: true });
    try {
      loadMain(stub, { serverStub: fakeServer().stub });
      stub.fireReady();
      await flush();
      assert.equal(stub.calls.errorBox.length, 1);
      assert.equal(stub.calls.errorBox[0][0], "OtterWorks failed to start");
      assert.match(stub.calls.errorBox[0][1], /Web build not found/);
      assert.deepEqual(stub.calls.exit, [1]);
      assert.equal(stub.calls.windows.length, 0);
    } finally {
      Object.defineProperty(process, "resourcesPath", { value: origRes, configurable: true, writable: true });
    }
  });

  test("server start failure shows an error dialog and exits 1", async () => {
    const stub = makeElectronStub();
    loadMain(stub, { serverStub: { startAppServer: async () => { throw new Error("listen EACCES"); } } });
    stub.fireReady();
    await flush();
    assert.deepEqual(stub.calls.errorBox, [["OtterWorks failed to start", "listen EACCES"]]);
    assert.deepEqual(stub.calls.exit, [1]);
  });
});

describe("navigation policy", () => {
  async function boot() {
    const stub = makeElectronStub();
    loadMain(stub, { serverStub: fakeServer().stub });
    stub.fireReady();
    await flush();
    return { stub, win: stub.calls.windows[0] };
  }

  test("window.open of http(s) URLs is denied and handed to the OS browser", async () => {
    const { stub, win } = await boot();
    assert.deepEqual(win.openHandler({ url: "https://docs.otterworks.app/help" }), { action: "deny" });
    assert.deepEqual(stub.calls.openExternal, ["https://docs.otterworks.app/help"]);
  });

  test("window.open of non-http schemes is denied and NOT opened externally", async () => {
    const { stub, win } = await boot();
    for (const u of ["file:///etc/passwd", "javascript:alert(1)", "smb://host/share"]) {
      assert.deepEqual(win.openHandler({ url: u }), { action: "deny" });
    }
    assert.deepEqual(stub.calls.openExternal, []);
  });

  test("same-origin navigation is allowed", async () => {
    const { stub, win } = await boot();
    let prevented = false;
    win.wcEvents["will-navigate"]({ preventDefault: () => (prevented = true) }, "http://127.0.0.1:34117/files");
    assert.equal(prevented, false);
    assert.deepEqual(stub.calls.openExternal, []);
  });

  test("cross-origin navigation is blocked and opened externally", async () => {
    const { stub, win } = await boot();
    let prevented = false;
    win.wcEvents["will-navigate"]({ preventDefault: () => (prevented = true) }, "https://evil.example/phish");
    assert.equal(prevented, true);
    assert.deepEqual(stub.calls.openExternal, ["https://evil.example/phish"]);
  });

  test("same host on a different port counts as cross-origin", async () => {
    const { win } = await boot();
    let prevented = false;
    win.wcEvents["will-navigate"]({ preventDefault: () => (prevented = true) }, "http://127.0.0.1:8080/api/v1/files");
    assert.equal(prevented, true);
  });

  test("cross-origin file:// navigation is blocked without openExternal", async () => {
    const { stub, win } = await boot();
    let prevented = false;
    win.wcEvents["will-navigate"]({ preventDefault: () => (prevented = true) }, "file:///etc/passwd");
    assert.equal(prevented, true);
    assert.deepEqual(stub.calls.openExternal, []);
  });
});

describe("app lifecycle", () => {
  test("second instance quits immediately when the single-instance lock is held", async () => {
    const stub = makeElectronStub({ lock: false });
    loadMain(stub, { serverStub: fakeServer().stub });
    stub.fireReady();
    await flush();
    assert.equal(stub.calls.quit, 1);
    assert.equal(stub.calls.windows.length, 0);
  });

  test("second-instance restores and focuses the existing window", async () => {
    const stub = makeElectronStub();
    loadMain(stub, { serverStub: fakeServer().stub });
    stub.fireReady();
    await flush();
    const win = stub.calls.windows[0];
    win.minimized = true;
    stub.events["second-instance"]();
    assert.equal(win.restored, 1);
    assert.equal(win.focused, 1);
    win.minimized = false;
    stub.events["second-instance"]();
    assert.equal(win.restored, 1);
    assert.equal(win.focused, 2);
  });

  test("window-all-closed quits on non-macOS", async () => {
    const stub = makeElectronStub();
    loadMain(stub, { serverStub: fakeServer().stub });
    stub.fireReady();
    await flush();
    stub.events["window-all-closed"]();
    assert.equal(stub.calls.quit, process.platform === "darwin" ? 0 : 1);
  });

  test("activate re-creates a window when none are open", async () => {
    const stub = makeElectronStub();
    loadMain(stub, { serverStub: fakeServer().stub });
    stub.fireReady();
    await flush();
    stub.module.BrowserWindow.all.length = 0;
    stub.events["activate"]();
    assert.equal(stub.calls.windows.length, 2);
    assert.equal(stub.calls.windows[1].loaded, "http://127.0.0.1:34117");
  });

  test("activate does nothing while a window is open", async () => {
    const stub = makeElectronStub();
    loadMain(stub, { serverStub: fakeServer().stub });
    stub.fireReady();
    await flush();
    stub.events["activate"]();
    assert.equal(stub.calls.windows.length, 1);
  });

  test("quit closes the embedded server", async () => {
    const stub = makeElectronStub();
    const srv = fakeServer();
    loadMain(stub, { serverStub: srv.stub });
    stub.fireReady();
    await flush();
    stub.events["quit"]();
    await flush();
    assert.equal(srv.closes.n, 1);
  });

  test("--smoke-test exits 0 on did-finish-load and 1 on did-fail-load", async () => {
    process.argv = [...savedArgv, "--smoke-test"];
    const stub = makeElectronStub();
    loadMain(stub, { serverStub: fakeServer().stub });
    stub.fireReady();
    await flush();
    const win = stub.calls.windows[0];
    win.wcOnce["did-finish-load"]();
    assert.deepEqual(stub.calls.exit, [0]);
    win.wcOnce["did-fail-load"]({}, -102, "ERR_CONNECTION_REFUSED");
    assert.deepEqual(stub.calls.exit, [0, 1]);
  });
});
