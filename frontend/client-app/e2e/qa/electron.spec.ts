import { test, expect, _electron as electron, type ElectronApplication, type Page } from "@playwright/test";
import path from "node:path";
import net from "node:net";
import { createRequire } from "node:module";

// Critical-path E2E for the OtterWorks Electron desktop app.
// Run: npx playwright test -c e2e/qa/playwright.electron.config.ts

const DESKTOP_DIR = path.resolve(__dirname, "..", "..", "desktop");
const GATEWAY = process.env.API_GATEWAY_URL || "http://localhost:8080";
const PASSWORD = "Passw0rd!23";
// The electron package lives in desktop/node_modules; require() returns the binary path.
const ELECTRON_BIN: string = createRequire(path.join(DESKTOP_DIR, "package.json"))("electron");

async function freePort(): Promise<number> {
  return new Promise((resolve) => {
    const s = net.createServer();
    s.listen(0, "127.0.0.1", () => {
      const port = (s.address() as net.AddressInfo).port;
      s.close(() => resolve(port));
    });
  });
}

async function launch(env: Record<string, string> = {}): Promise<{ app: ElectronApplication; win: Page }> {
  const childEnv: Record<string, string> = { ...(process.env as Record<string, string>), ...env };
  delete childEnv.ELECTRON_RUN_AS_NODE;
  const app = await electron.launch({
    executablePath: ELECTRON_BIN,
    cwd: DESKTOP_DIR,
    args: [DESKTOP_DIR, "--no-sandbox"],
    env: childEnv,
  });
  const win = await app.firstWindow();
  await win.waitForLoadState("domcontentloaded");
  return { app, win };
}

async function apiRegister(prefix: string) {
  const email = `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@otterworks.test`;
  const res = await fetch(`${GATEWAY}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password: PASSWORD, displayName: "QA Electron E2E" }),
  });
  expect(res.status).toBe(201);
  const data = await res.json();
  return { email, id: data.user.id as string, token: data.accessToken as string };
}

async function uiLogin(win: Page, email: string) {
  await win.evaluate(() => window.history.pushState({}, "", "/login"));
  await win.reload();
  await win.getByLabel("Email").fill(email);
  await win.getByLabel("Password").fill(PASSWORD);
  await win.getByRole("button", { name: "Sign in" }).click();
  await expect(win).toHaveURL(/\/dashboard/);
  await expect(win.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

test.describe.serial("electron desktop app", () => {
  let user: Awaited<ReturnType<typeof apiRegister>>;
  let port: number;

  test.beforeAll(async () => {
    user = await apiRegister("qa-electron");
    port = await freePort();
  });

  test("boots one secure window on the embedded local server", async () => {
    const { app, win } = await launch({ OTTER_DESKTOP_PORT: String(port) });
    try {
      expect(app.windows()).toHaveLength(1);
      await expect(win).toHaveTitle("OtterWorks");
      expect(win.url()).toBe(`http://127.0.0.1:${port}/`);
      const prefs = await app.evaluate(({ BrowserWindow }) => {
        const w = BrowserWindow.getAllWindows()[0];
        const p = w.webContents.getLastWebPreferences()!;
        const [width, height] = w.getSize();
        return { contextIsolation: p.contextIsolation, nodeIntegration: p.nodeIntegration, sandbox: p.sandbox, width, height };
      });
      expect(prefs).toMatchObject({ contextIsolation: true, nodeIntegration: false, sandbox: true });
      expect(prefs.width).toBeGreaterThan(0);
      // No Node globals leak into the renderer
      expect(await win.evaluate(() => typeof (window as any).require)).toBe("undefined");
      expect(await win.evaluate(() => typeof (window as any).process)).toBe("undefined");
    } finally {
      await app.close();
    }
  });

  test("application menu exposes File/Edit/View/Window menus with reload", async () => {
    const { app } = await launch({ OTTER_DESKTOP_PORT: String(port) });
    try {
      const menu = await app.evaluate(({ Menu }) => {
        const m = Menu.getApplicationMenu();
        return m ? m.items.map((i) => ({ label: i.label.replace("&", ""), sub: i.submenu?.items.map((s) => s.role || s.label) ?? [] })) : null;
      });
      expect(menu).not.toBeNull();
      const labels = menu!.map((m) => m.label);
      for (const l of ["File", "Edit", "View", "Window"]) expect(labels).toContain(l);
      const view = menu!.find((m) => m.label === "View")!;
      expect(view.sub.map((s) => String(s).toLowerCase())).toEqual(expect.arrayContaining(["reload", "togglefullscreen"]));
    } finally {
      await app.close();
    }
  });

  test("login, files list, open a document and sidebar navigation", async () => {
    // Seed a file and a document for the user through the gateway
    const form = new FormData();
    form.append("file", new Blob(["electron e2e file"], { type: "text/plain" }), "electron-e2e.txt");
    const up = await fetch(`${GATEWAY}/api/v1/files/upload`, { method: "POST", headers: { Authorization: `Bearer ${user.token}` }, body: form });
    expect(up.status).toBe(201);
    const docRes = await fetch(`${GATEWAY}/api/v1/documents/`, {
      method: "POST",
      headers: { Authorization: `Bearer ${user.token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Electron E2E Doc", content: "<p>hello desktop</p>" }),
    });
    expect(docRes.status).toBe(201);
    const doc = await docRes.json();

    const { app, win } = await launch({ OTTER_DESKTOP_PORT: String(port) });
    try {
      await uiLogin(win, user.email);
      expect(await win.evaluate(() => !!localStorage.getItem("otter_access_token"))).toBe(true);

      await win.getByRole("link", { name: "Files", exact: true }).first().click();
      await expect(win).toHaveURL(/\/files$/);
      await expect(win.getByRole("heading", { name: "Files", level: 1 })).toBeVisible();
      await expect(win.getByText("electron-e2e.txt").first()).toBeVisible();

      await win.getByRole("link", { name: "Documents", exact: true }).first().click();
      await expect(win.getByRole("heading", { name: "Documents", level: 1 })).toBeVisible();
      await win.getByText("Electron E2E Doc").first().click();
      await expect(win).toHaveURL(new RegExp(`/documents/${doc.id}`));
      await expect(win.getByRole("heading", { name: /Electron E2E Doc/ })).toBeVisible();

      // Back/forward history and deep-link reload (SPA fallback through the embedded server)
      await win.goBack();
      await expect(win).toHaveURL(/\/documents$/);
      await win.goForward();
      await expect(win).toHaveURL(new RegExp(`/documents/${doc.id}`));
      await win.reload();
      await expect(win.getByRole("heading", { name: /Electron E2E Doc/ })).toBeVisible();
    } finally {
      await app.close();
    }
  });

  test("session survives an app restart (fixed local port keeps localStorage)", async () => {
    const { app, win } = await launch({ OTTER_DESKTOP_PORT: String(port) });
    try {
      await win.evaluate(() => window.history.pushState({}, "", "/dashboard"));
      await win.reload();
      await expect(win.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    } finally {
      await app.close();
    }
  });

  test("external links and cross-origin navigation never replace the app window", async () => {
    const { app, win } = await launch({ OTTER_DESKTOP_PORT: String(port) });
    try {
      await app.evaluate(({ shell }) => {
        (globalThis as any).__opened = [];
        shell.openExternal = async (u: string) => void (globalThis as any).__opened.push(u);
      });
      const origin = new URL(win.url()).origin;
      await win.evaluate(() => window.open("https://example.com/help", "_blank"));
      await win.evaluate(() => { window.location.href = "https://example.org/phish"; });
      await win.waitForTimeout(1000);
      expect(app.windows()).toHaveLength(1);
      expect(new URL(win.url()).origin).toBe(origin);
      const opened = await app.evaluate(() => (globalThis as any).__opened);
      expect(opened).toEqual(["https://example.com/help", "https://example.org/phish"]);
    } finally {
      await app.close();
    }
  });

  test("offline gateway: UI still loads and login shows an error", async () => {
    const deadPort = await freePort();
    const { app, win } = await launch({ OTTER_DESKTOP_PORT: String(await freePort()), API_GATEWAY_URL: `http://127.0.0.1:${deadPort}` });
    try {
      await win.evaluate(() => window.history.pushState({}, "", "/login"));
      await win.reload();
      await win.getByLabel("Email").fill(user.email);
      await win.getByLabel("Password").fill(PASSWORD);
      const resp = win.waitForResponse((r) => r.url().includes("/api/v1/auth/login"));
      await win.getByRole("button", { name: "Sign in" }).click();
      expect((await resp).status()).toBe(502);
      await expect(win.getByText("Invalid email or password. Please try again.")).toBeVisible();
      await expect(win).toHaveURL(/\/login/);
    } finally {
      await app.close();
    }
  });

  test("second launch focuses the existing instance instead of opening a new window", async () => {
    const first = await launch({ OTTER_DESKTOP_PORT: String(port) });
    try {
      const childEnv = { ...process.env } as Record<string, string>;
      delete childEnv.ELECTRON_RUN_AS_NODE;
      const second = await electron.launch({ executablePath: ELECTRON_BIN, cwd: DESKTOP_DIR, args: [DESKTOP_DIR, "--no-sandbox"], env: childEnv }).catch(() => null);
      if (second) {
        await second.waitForEvent("close", { timeout: 10_000 }).catch(() => {});
      }
      expect(first.app.windows()).toHaveLength(1);
    } finally {
      await first.app.close();
    }
  });
});
