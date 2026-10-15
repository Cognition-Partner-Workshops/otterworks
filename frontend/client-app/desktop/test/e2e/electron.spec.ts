import { test, expect, _electron as electron, type ElectronApplication, type Page } from "@playwright/test";
import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";

const DESKTOP_DIR = path.resolve(__dirname, "..", "..");
// eslint-disable-next-line @typescript-eslint/no-var-requires
const ELECTRON_BIN: string = require(path.join(DESKTOP_DIR, "node_modules", "electron"));
const GATEWAY_URL = process.env.API_GATEWAY_URL || "http://localhost:8080";
const PASSWORD = "OtterworksTest123!";

type Launch = { app: ElectronApplication; window: Page; port: number; userDataDir: string };

async function freePort(): Promise<number> {
  return new Promise((resolve) => {
    const srv = net.createServer().listen(0, "127.0.0.1", () => {
      const { port } = srv.address() as net.AddressInfo;
      srv.close(() => resolve(port));
    });
  });
}

function cleanEnv(extra: Record<string, string>): Record<string, string> {
  const env: Record<string, string> = {};
  for (const [k, v] of Object.entries(process.env)) if (v !== undefined) env[k] = v;
  delete env.ELECTRON_RUN_AS_NODE;
  return { ...env, ...extra };
}

async function launch(opts: { port?: number; userDataDir?: string; gateway?: string } = {}): Promise<Launch> {
  const port = opts.port ?? (await freePort());
  const userDataDir = opts.userDataDir ?? fs.mkdtempSync(path.join(os.tmpdir(), "otter-desktop-e2e-"));
  const app = await electron.launch({
    executablePath: ELECTRON_BIN,
    args: [DESKTOP_DIR, `--user-data-dir=${userDataDir}`],
    cwd: DESKTOP_DIR,
    env: cleanEnv({ API_GATEWAY_URL: opts.gateway ?? GATEWAY_URL, OTTER_DESKTOP_PORT: String(port) }),
  });
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");
  return { app, window, port, userDataDir };
}

async function gatewayUp(): Promise<boolean> {
  try {
    return (await fetch(`${GATEWAY_URL}/health`)).ok;
  } catch {
    return false;
  }
}

async function seedUser() {
  const email = `desktop-e2e-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.test`;
  const reg = await fetch(`${GATEWAY_URL}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: PASSWORD, displayName: "Desktop E2E" }),
  });
  expect(reg.status).toBe(201);
  const { accessToken } = await reg.json();
  const auth = { Authorization: `Bearer ${accessToken}` };
  const docTitle = `Desktop E2E doc ${Date.now()}`;
  const doc = await fetch(`${GATEWAY_URL}/api/v1/documents/`, {
    method: "POST",
    headers: { ...auth, "Content-Type": "application/json" },
    body: JSON.stringify({ title: docTitle, content: "Opened from the Electron shell" }),
  });
  expect(doc.status).toBe(201);
  const fileName = `desktop-e2e-${Date.now()}.txt`;
  const form = new FormData();
  form.append("file", new Blob(["hello from desktop e2e"], { type: "text/plain" }), fileName);
  const upload = await fetch(`${GATEWAY_URL}/api/v1/files/upload`, { method: "POST", headers: auth, body: form });
  expect(upload.status).toBe(201);
  return { email, docTitle, fileName };
}

async function login(window: Page, email: string) {
  await window.goto(new URL("/login", window.url()).toString());
  await window.getByLabel("Email").fill(email);
  await window.getByLabel("Password").fill(PASSWORD);
  await window.getByRole("button", { name: "Sign in" }).click();
}

test.describe("Electron shell (no backend required)", () => {
  test("opens a single 1280x800 OtterWorks window on the embedded loopback server", async () => {
    const { app, window, port } = await launch();
    try {
      expect(window.url()).toBe(`http://127.0.0.1:${port}/`);
      await expect(window).toHaveTitle(/OtterWorks/);
      await expect(window.getByRole("heading", { name: "OtterWorks", exact: true })).toBeVisible();
      const info = await app.evaluate(({ BrowserWindow }) => {
        const wins = BrowserWindow.getAllWindows();
        const [w] = wins;
        return { count: wins.length, bounds: w.getBounds(), title: w.getTitle() };
      });
      expect(info.count).toBe(1);
      expect(info.bounds.width).toBe(1280);
      expect(info.bounds.height).toBe(800);
    } finally {
      await app.close();
    }
  });

  test("renderer is sandboxed with context isolation and no Node integration", async () => {
    const { app, window } = await launch();
    try {
      const prefs = await app.evaluate(({ BrowserWindow }) => {
        const p = BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences();
        return { contextIsolation: p?.contextIsolation, nodeIntegration: p?.nodeIntegration, sandbox: p?.sandbox };
      });
      expect(prefs).toEqual({ contextIsolation: true, nodeIntegration: false, sandbox: true });
      const globals = await window.evaluate(() => ({
        require: typeof (window as unknown as { require?: unknown }).require,
        process: typeof (window as unknown as { process?: unknown }).process,
      }));
      expect(globals).toEqual({ require: "undefined", process: "undefined" });
    } finally {
      await app.close();
    }
  });

  test("SPA deep links load via the index.html fallback", async () => {
    const { app, window } = await launch();
    try {
      await window.goto(new URL("/login", window.url()).toString());
      await expect(window.getByText("Sign in to your account")).toBeVisible();
      await window.goto(new URL("/register", window.url()).toString());
      await expect(window.getByText("Create your account")).toBeVisible();
    } finally {
      await app.close();
    }
  });

  test("window.open to external URLs is denied and handed to the OS browser", async () => {
    const { app, window } = await launch();
    try {
      await app.evaluate(({ shell }) => {
        const g = globalThis as unknown as { __opened: string[] };
        g.__opened = [];
        shell.openExternal = async (url: string) => {
          g.__opened.push(url);
        };
      });
      await window.evaluate(() => window.open("https://example.com/docs", "_blank"));
      await window.waitForTimeout(500);
      const result = await app.evaluate(({ BrowserWindow }) => ({
        windows: BrowserWindow.getAllWindows().length,
        opened: (globalThis as unknown as { __opened: string[] }).__opened,
      }));
      expect(result.windows).toBe(1);
      expect(result.opened).toEqual(["https://example.com/docs"]);
    } finally {
      await app.close();
    }
  });

  test("navigating the main window off the app origin is blocked", async () => {
    const { app, window, port } = await launch();
    try {
      await app.evaluate(({ shell }) => {
        const g = globalThis as unknown as { __opened: string[] };
        g.__opened = [];
        shell.openExternal = async (url: string) => {
          g.__opened.push(url);
        };
      });
      await window.evaluate(() => {
        window.location.href = "https://example.com/phish";
      });
      await window.waitForTimeout(1000);
      expect(new URL(window.url()).origin).toBe(`http://127.0.0.1:${port}`);
      const opened = await app.evaluate(() => (globalThis as unknown as { __opened: string[] }).__opened);
      expect(opened).toEqual(["https://example.com/phish"]);
    } finally {
      await app.close();
    }
  });

  test("window can be resized, minimized and restored; layout follows the viewport", async () => {
    const { app, window } = await launch();
    try {
      await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].setSize(820, 640));
      await expect.poll(() => window.evaluate(() => window.innerWidth)).toBeLessThanOrEqual(820);
      await expect(window.getByRole("heading", { name: "OtterWorks", exact: true })).toBeVisible();
      const state = await app.evaluate(async ({ BrowserWindow }) => {
        const w = BrowserWindow.getAllWindows()[0];
        w.minimize();
        await new Promise((r) => setTimeout(r, 500));
        w.restore();
        await new Promise((r) => setTimeout(r, 500));
        return { visible: w.isVisible(), minimized: w.isMinimized(), size: w.getSize() };
      });
      expect(state.visible).toBe(true);
      expect(state.minimized).toBe(false);
      expect(state.size).toEqual([820, 640]);
    } finally {
      await app.close();
    }
  });

  test("has the standard application menu (File/Edit/View/Window) with Reload and DevTools", async () => {
    const { app } = await launch();
    try {
      const menu = await app.evaluate(({ Menu }) => {
        const m = Menu.getApplicationMenu();
        return {
          top: m?.items.map((i) => i.label.replace(/&/g, "")) ?? [],
          roles: m?.items.flatMap((i) => i.submenu?.items.map((s) => s.role ?? "") ?? []) ?? [],
        };
      });
      for (const label of ["File", "Edit", "View", "Window"]) expect(menu.top).toContain(label);
      for (const role of ["reload", "toggledevtools", "copy", "paste", "quit"]) {
        expect(menu.roles.map((r) => r.toLowerCase())).toContain(role);
      }
    } finally {
      await app.close();
    }
  });

  test("closing the last window quits the app (Linux/Windows)", async () => {
    test.skip(process.platform === "darwin", "macOS keeps the app alive after the last window closes");
    const { app } = await launch();
    const exited = new Promise<number | null>((resolve) => app.process().once("exit", (code) => resolve(code)));
    await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].close());
    expect(await Promise.race([exited, new Promise((r) => setTimeout(() => r("still running"), 10_000))])).toBe(0);
  });

  test("falls back to an ephemeral port when the preferred port is taken", async () => {
    const blocker = net.createServer();
    const taken = await new Promise<number>((r) =>
      blocker.listen(0, "127.0.0.1", () => r((blocker.address() as net.AddressInfo).port))
    );
    const { app, window } = await launch({ port: taken });
    try {
      const port = Number(new URL(window.url()).port);
      expect(port).not.toBe(taken);
      await expect(window.getByRole("heading", { name: "OtterWorks", exact: true })).toBeVisible();
    } finally {
      await app.close();
      blocker.close();
    }
  });

  test("a second instance exits and focuses the running window", async () => {
    const first = await launch();
    try {
      const second = spawn(ELECTRON_BIN, [DESKTOP_DIR, `--user-data-dir=${first.userDataDir}`], {
        cwd: DESKTOP_DIR,
        env: cleanEnv({ OTTER_DESKTOP_PORT: String(await freePort()) }),
        stdio: "ignore",
      });
      const code = await new Promise<number | null | string>((resolve) => {
        second.once("exit", (c) => resolve(c));
        setTimeout(() => {
          second.kill();
          resolve("still running");
        }, 15_000);
      });
      expect(code).toBe(0);
      const count = await first.app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().length);
      expect(count).toBe(1);
    } finally {
      await first.app.close();
    }
  });

  test("backend down: proxy answers 502 and the login form stays usable", async () => {
    const { app, window } = await launch({ gateway: `http://127.0.0.1:${await freePort()}` });
    try {
      const status = await window.evaluate(async () => {
        const r = await fetch("/api/v1/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        return { status: r.status, body: await r.json() };
      });
      expect(status.status).toBe(502);
      expect(status.body.error).toBe("bad_gateway");
      await login(window, "nobody@example.test");
      await expect(window.getByRole("alert").or(window.locator(".text-red-600, .text-red-700")).first()).toBeVisible();
      await expect(window).toHaveURL(/\/login/);
      await expect(window.getByRole("button", { name: "Sign in" })).toBeEnabled();
    } finally {
      await app.close();
    }
  });

  test("[REAL] backend down: login says the service is unreachable, not 'Invalid email or password'", async () => {
    const { app, window } = await launch({ gateway: `http://127.0.0.1:${await freePort()}` });
    try {
      await login(window, "nobody@example.test");
      await window.waitForTimeout(2000);
      await expect(window.getByText("Invalid email or password. Please try again.")).toHaveCount(0);
    } finally {
      await app.close();
    }
  });

  test("[REAL] backend down: signed-in Files page reports an error instead of 'This folder is empty'", async () => {
    const { app, window } = await launch({ gateway: `http://127.0.0.1:${await freePort()}` });
    try {
      await window.evaluate(() => {
        localStorage.setItem("otter_access_token", "offline-test-token");
      });
      await window.goto(new URL("/files", window.url()).toString());
      await expect(window.getByRole("heading", { name: "Files" })).toBeVisible();
      await window.waitForTimeout(3000);
      await expect(window.getByText("This folder is empty")).toHaveCount(0);
    } finally {
      await app.close();
    }
  });
});

test.describe("Electron shell against the local stack", () => {
  test.beforeEach(async () => {
    test.skip(!(await gatewayUp()), `API gateway not reachable at ${GATEWAY_URL}`);
  });

  test("login, browse files, open a document; session survives relaunch", async () => {
    const seeded = await seedUser();
    const first = await launch();
    try {
      await login(first.window, seeded.email);
      await expect(first.window).toHaveURL(/\/dashboard/, { timeout: 20_000 });
      await expect(first.window.getByRole("heading", { name: "Dashboard" })).toBeVisible();

      await first.window.getByRole("link", { name: "Files", exact: true }).first().click();
      await expect(first.window.getByRole("heading", { name: "Files" })).toBeVisible();
      await expect(first.window.getByText(seeded.fileName).first()).toBeVisible();

      await first.window.getByRole("link", { name: "Documents", exact: true }).first().click();
      await expect(first.window.getByRole("heading", { name: "Documents" })).toBeVisible();
      await first.window.getByText(seeded.docTitle).first().click();
      await expect(first.window).toHaveURL(/\/documents\/[^/]+/);
      await expect(first.window.getByRole("heading", { name: seeded.docTitle })).toBeVisible();
    } finally {
      await first.app.close();
    }

    // Same port + profile => same localStorage origin => still signed in.
    const second = await launch({ port: first.port, userDataDir: first.userDataDir });
    try {
      await second.window.goto(new URL("/dashboard", second.window.url()).toString());
      await expect(second.window.getByRole("heading", { name: "Dashboard" })).toBeVisible();
      await expect(second.window).toHaveURL(/\/dashboard/);
    } finally {
      await second.app.close();
    }
  });
});
