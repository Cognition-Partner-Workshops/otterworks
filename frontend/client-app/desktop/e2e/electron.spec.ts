import { test, expect, type ElectronApplication } from "@playwright/test";
import { spawn, spawnSync, execFileSync } from "node:child_process";
import net from "node:net";
import {
  DESKTOP_DIR,
  ELECTRON_BIN,
  ToggleableGateway,
  appUrl,
  createDocument,
  createFolder,
  desktopEnv,
  freePort,
  freshUserDataDir,
  getDocument,
  launchDesktop,
  registerViaGateway,
  signInWithTokens,
  uploadFile,
} from "./desktop-helpers";

// End-to-end coverage of the OtterWorks Electron shell (src/main.ts + src/server.ts)
// against a live local stack. Bugs found during QA are kept as test.fail() with the
// DESKTOP-xx reference so the suite stays green until they are fixed.

let app: ElectronApplication | undefined;

test.afterEach(async () => {
  await app?.close().catch(() => {});
  app = undefined;
});

test.describe("launch and window", () => {
  test("opens a 1280x800 OtterWorks window served from the embedded loopback server", async () => {
    const launched = await launchDesktop();
    app = launched.app;
    const { win, port } = launched;

    expect(win.url()).toBe(`http://127.0.0.1:${port}/`);
    await expect(win).toHaveTitle("OtterWorks");
    await expect(win.getByRole("heading", { level: 1 }).first()).toBeVisible();

    const info = await app.evaluate(({ BrowserWindow }) => {
      const windows = BrowserWindow.getAllWindows();
      const [w] = windows;
      return { count: windows.length, bounds: w.getBounds(), visible: w.isVisible() };
    });
    expect(info.count).toBe(1);
    expect(info.visible).toBe(true);
    expect(info.bounds.width).toBe(1280);
    expect(info.bounds.height).toBe(800);
  });

  test("renderer is sandboxed with context isolation and no Node integration", async () => {
    const launched = await launchDesktop();
    app = launched.app;
    const prefs = await app.evaluate(({ BrowserWindow }) => {
      const p = BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences();
      return { contextIsolation: p?.contextIsolation, nodeIntegration: p?.nodeIntegration, sandbox: p?.sandbox };
    });
    expect(prefs).toEqual({ contextIsolation: true, nodeIntegration: false, sandbox: true });
    const globals = await launched.win.evaluate(() => ({
      require: typeof (window as unknown as { require?: unknown }).require,
      process: typeof (window as unknown as { process?: unknown }).process,
    }));
    expect(globals).toEqual({ require: "undefined", process: "undefined" });
  });

  test("exposes the default application menu (File/Edit/View/Window)", async () => {
    test.skip(process.platform === "darwin", "macOS adds the app menu and Help");
    const launched = await launchDesktop();
    app = launched.app;
    const menu = await app.evaluate(({ Menu }) =>
      Menu.getApplicationMenu()?.items.map((i) => ({
        label: i.label,
        items: i.submenu?.items.filter((s) => s.type !== "separator").map((s) => s.label) ?? [],
      }))
    );
    expect(menu?.map((m) => m.label)).toEqual(["File", "Edit", "View", "Window"]);
    const byLabel = Object.fromEntries((menu ?? []).map((m) => [m.label, m.items]));
    expect(byLabel.File).toContain("Quit");
    expect(byLabel.Edit).toEqual(expect.arrayContaining(["Undo", "Redo", "Cut", "Copy", "Paste", "Select All"]));
    expect(byLabel.View).toEqual(expect.arrayContaining(["Reload", "Zoom In", "Zoom Out", "Toggle Full Screen"]));
    expect(byLabel.Window).toEqual(expect.arrayContaining(["Minimize", "Close"]));
  });

  test("--smoke-test loads the web build and exits 0", async () => {
    const port = await freePort();
    const result = spawnSync(ELECTRON_BIN, [DESKTOP_DIR, `--user-data-dir=${freshUserDataDir()}`, "--smoke-test"], {
      cwd: DESKTOP_DIR,
      env: desktopEnv({ OTTER_DESKTOP_PORT: String(port) }),
      encoding: "utf8",
      timeout: 40_000,
    });
    expect(result.status).toBe(0);
    expect(result.stdout).toContain(`smoke test ok: loaded http://127.0.0.1:${port}`);
  });
});

test.describe("authentication", () => {
  test("signs in through the UI via the same-origin /api/v1 proxy and signs out", async () => {
    const user = await registerViaGateway();
    const launched = await launchDesktop();
    app = launched.app;
    const { win, port } = launched;

    await win.goto(appUrl(win, "/login"));
    await win.getByLabel("Email").fill(user.email);
    await win.getByLabel("Password").fill(user.password);
    const loginRequest = win.waitForRequest((r) => r.url().endsWith("/api/v1/auth/login"));
    await win.getByRole("button", { name: "Sign in" }).click();
    expect(new URL((await loginRequest).url()).origin).toBe(`http://127.0.0.1:${port}`);

    await win.waitForURL((url) => url.pathname === "/dashboard");
    await expect(win.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    expect(await win.evaluate(() => !!localStorage.getItem("otter_access_token"))).toBe(true);

    await win.getByRole("button", { name: "Sign out" }).click();
    await win.waitForURL((url) => url.pathname === "/login");
    expect(await win.evaluate(() => localStorage.getItem("otter_access_token"))).toBeNull();
  });

  test("rejects a wrong password with an inline error", async () => {
    const user = await registerViaGateway();
    const launched = await launchDesktop();
    app = launched.app;
    const { win } = launched;
    await win.goto(appUrl(win, "/login"));
    await win.getByLabel("Email").fill(user.email);
    await win.getByLabel("Password").fill("definitely-wrong-password");
    await win.getByRole("button", { name: "Sign in" }).click();
    await expect(win.getByText("Invalid email or password")).toBeVisible();
    expect(new URL(win.url()).pathname).toBe("/login");
  });

  test("keeps the session across restarts (same profile + fixed port)", async () => {
    const user = await registerViaGateway();
    const userDataDir = freshUserDataDir();
    const port = await freePort();

    const first = await launchDesktop({ userDataDir, port });
    app = first.app;
    await signInWithTokens(first.win, user);
    await first.app.close();

    const second = await launchDesktop({ userDataDir, port });
    app = second.app;
    expect(second.win.url()).toBe(`http://127.0.0.1:${port}/`);
    await second.win.goto(appUrl(second.win, "/dashboard"));
    await expect(second.win.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(second.win.getByText(user.email)).toBeVisible();
  });
});

test.describe("files and documents", () => {
  test("browses folders and files and opens file details", async () => {
    const user = await registerViaGateway();
    const stamp = Date.now();
    const folder = await createFolder(user, `Desktop Folder ${stamp}`);
    const file = await uploadFile(user, `desktop-notes-${stamp}.txt`, "hello from the desktop e2e");

    const launched = await launchDesktop();
    app = launched.app;
    const { win } = launched;
    await signInWithTokens(win, user);
    await win.goto(appUrl(win, "/files"));

    await expect(win.getByRole("heading", { name: "Files" })).toBeVisible();
    await expect(win.getByText(folder.name).first()).toBeVisible();
    await expect(win.getByText(file.name).first()).toBeVisible();

    await win.getByText(folder.name).first().click();
    await win.waitForURL((url) => url.searchParams.get("folder") === folder.id);

    await win.goto(appUrl(win, "/files"));
    await win.getByText(file.name).first().click();
    await win.waitForURL((url) => url.pathname === `/files/${file.id}`);
    await expect(win.getByText(file.name).first()).toBeVisible();
  });

  test("edits a document and the change is persisted server-side", async () => {
    const user = await registerViaGateway();
    const doc = await createDocument(user, `Desktop Doc ${Date.now()}`, "<p>Initial body</p>");

    const launched = await launchDesktop();
    app = launched.app;
    const { win } = launched;
    await signInWithTokens(win, user);
    await win.goto(appUrl(win, "/documents"));
    await win.getByText(doc.title).first().click();
    await win.waitForURL((url) => url.pathname === `/documents/${doc.id}`);

    const editor = win.locator(".ProseMirror");
    await expect(editor).toContainText("Initial body");
    await expect(win.getByText("All changes saved")).toBeVisible();

    await editor.click();
    await win.keyboard.press("End");
    await win.keyboard.type(" edited in Electron");
    await expect(editor).toContainText("Initial body edited in Electron");
    await expect(win.getByText("All changes saved")).toBeVisible();

    await expect
      .poll(async () => (await getDocument(user, doc.id)).content, { timeout: 20_000 })
      .toContain("edited in Electron");
  });
});

test.describe("offline and reconnect", () => {
  test("API gateway outage surfaces 502s and the app recovers when it returns", async () => {
    const user = await registerViaGateway();
    const file = await uploadFile(user, `offline-${Date.now()}.txt`, "offline test");
    const gateway = new ToggleableGateway();
    await gateway.start();
    try {
      const launched = await launchDesktop({ env: { API_GATEWAY_URL: gateway.url } });
      app = launched.app;
      const { win } = launched;
      await signInWithTokens(win, user);
      await win.goto(appUrl(win, "/files"));
      await expect(win.getByText(file.name).first()).toBeVisible();

      gateway.goOffline();
      const offline = await win.evaluate(async () => {
        const r = await fetch("/api/v1/files", {
          headers: { Authorization: `Bearer ${localStorage.getItem("otter_access_token")}` },
        });
        return { status: r.status, body: await r.json() };
      });
      expect(offline.status).toBe(502);
      expect(offline.body.error).toBe("bad_gateway");
      // The embedded server keeps serving the SPA shell while the backend is down.
      await win.reload();
      await expect(win.getByRole("heading", { name: "Files" })).toBeVisible();

      gateway.goOnline();
      await win.reload();
      await expect(win.getByText(file.name).first()).toBeVisible();
    } finally {
      await gateway.stop();
    }
  });

  test("collab disconnect shows Reconnecting… and offline edits sync after reconnect", async () => {
    const container = process.env.OTTER_COLLAB_CONTAINER || "otterworks-collab-service";
    let dockerOk = true;
    try {
      execFileSync("docker", ["inspect", container], { stdio: "ignore" });
    } catch {
      dockerOk = false;
    }
    test.skip(!dockerOk, `needs docker access to ${container}`);

    const user = await registerViaGateway();
    const doc = await createDocument(user, `Reconnect Doc ${Date.now()}`, "<p>before outage</p>");
    const launched = await launchDesktop();
    app = launched.app;
    const { win } = launched;
    await signInWithTokens(win, user);
    await win.goto(appUrl(win, `/documents/${doc.id}`));
    await expect(win.getByText("All changes saved")).toBeVisible();

    execFileSync("docker", ["stop", container], { stdio: "ignore" });
    try {
      await expect(win.getByText("Reconnecting…")).toBeVisible();
      const editor = win.locator(".ProseMirror");
      await editor.click();
      await win.keyboard.press("End");
      await win.keyboard.type(" typed while offline");
    } finally {
      execFileSync("docker", ["start", container], { stdio: "ignore" });
    }
    await expect(win.getByText("All changes saved")).toBeVisible({ timeout: 60_000 });
    await expect
      .poll(async () => (await getDocument(user, doc.id)).content, { timeout: 30_000 })
      .toContain("typed while offline");
  });
});

test.describe("single-instance lock", () => {
  test("a second launch with the same profile exits and focuses the existing window", async () => {
    const launched = await launchDesktop();
    app = launched.app;
    await app.evaluate(({ app: electronApp, BrowserWindow }) => {
      (globalThis as unknown as { secondInstances: number }).secondInstances = 0;
      electronApp.on("second-instance", () => {
        (globalThis as unknown as { secondInstances: number }).secondInstances++;
      });
      BrowserWindow.getAllWindows()[0].minimize();
    });

    const second = spawn(ELECTRON_BIN, [DESKTOP_DIR, `--user-data-dir=${launched.userDataDir}`], {
      cwd: DESKTOP_DIR,
      env: desktopEnv({ OTTER_DESKTOP_PORT: String(launched.port) }),
      stdio: "ignore",
    });
    const exitCode = await new Promise<number | null>((resolve) => {
      const timer = setTimeout(() => {
        second.kill();
        resolve(-1);
      }, 15_000);
      second.on("exit", (code) => {
        clearTimeout(timer);
        resolve(code);
      });
    });
    expect(exitCode).toBe(0);

    await expect
      .poll(() =>
        app!.evaluate(({ BrowserWindow }) => ({
          secondInstances: (globalThis as unknown as { secondInstances: number }).secondInstances,
          windows: BrowserWindow.getAllWindows().length,
          minimized: BrowserWindow.getAllWindows()[0].isMinimized(),
        }))
      )
      .toEqual({ secondInstances: 1, windows: 1, minimized: false });
  });

  test("a different profile runs independently and falls back to a free port", async () => {
    const first = await launchDesktop();
    app = first.app;
    const second = await launchDesktop({ port: first.port });
    try {
      const secondPort = Number(new URL(second.win.url()).port);
      expect(secondPort).not.toBe(first.port);
      await expect(second.win).toHaveTitle("OtterWorks");
    } finally {
      await second.app.close();
    }
  });

  test("starts on an ephemeral port when OTTER_DESKTOP_PORT is taken", async () => {
    const blocker = net.createServer();
    await new Promise<void>((r) => blocker.listen(0, "127.0.0.1", r));
    const taken = (blocker.address() as net.AddressInfo).port;
    try {
      const launched = await launchDesktop({ port: taken });
      app = launched.app;
      expect(Number(new URL(launched.win.url()).port)).not.toBe(taken);
      await expect(launched.win).toHaveTitle("OtterWorks");
    } finally {
      blocker.close();
    }
  });
});

test.describe("navigation guard", () => {
  async function stubOpenExternal(electronApp: ElectronApplication) {
    await electronApp.evaluate(({ shell }) => {
      const g = globalThis as unknown as { opened: string[] };
      g.opened = [];
      shell.openExternal = async (url: string) => {
        g.opened.push(url);
      };
    });
  }
  const opened = (electronApp: ElectronApplication) =>
    electronApp.evaluate(() => (globalThis as unknown as { opened: string[] }).opened);

  test("external links open in the OS browser and never replace the app window", async () => {
    const launched = await launchDesktop();
    app = launched.app;
    const { win } = launched;
    await stubOpenExternal(app);
    const start = win.url();

    await win.evaluate(() => window.open("https://example.com/help", "_blank"));
    await win.evaluate(() => {
      const a = document.createElement("a");
      a.href = "https://example.org/docs";
      document.body.appendChild(a);
      a.click();
    });

    await expect.poll(() => opened(app!)).toEqual(["https://example.com/help", "https://example.org/docs"]);
    expect(win.url()).toBe(start);
    expect(app.windows()).toHaveLength(1);
  });

  test("non-http(s) popups are blocked without hand-off", async () => {
    const launched = await launchDesktop();
    app = launched.app;
    await stubOpenExternal(app);
    await launched.win.evaluate(() => window.open("file:///etc/passwd", "_blank"));
    await launched.win.waitForTimeout(500);
    expect(await opened(app)).toEqual([]);
    expect(app.windows()).toHaveLength(1);
  });

  test("same-origin popups stay in the app instead of opening the OS browser", async () => {
    test.fail(true, "[REAL] DESKTOP-04: setWindowOpenHandler hands same-origin URLs to shell.openExternal");
    const launched = await launchDesktop();
    app = launched.app;
    await stubOpenExternal(app);
    await launched.win.evaluate(() => window.open("/files", "_blank"));
    await launched.win.waitForTimeout(500);
    expect(await opened(app)).toEqual([]);
  });
});
