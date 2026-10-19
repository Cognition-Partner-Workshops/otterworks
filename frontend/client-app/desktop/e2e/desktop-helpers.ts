import { _electron, type ElectronApplication, type Page } from "@playwright/test";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";

export const DESKTOP_DIR = path.resolve(__dirname, "..");
// Resolved through Node: the electron package exports the binary path.
// eslint-disable-next-line @typescript-eslint/no-require-imports
export const ELECTRON_BIN: string = require(path.join(DESKTOP_DIR, "node_modules", "electron"));
export const GATEWAY_URL = (process.env.API_GATEWAY_URL || "http://localhost:8080").replace(/\/$/, "");
export const TEST_PASSWORD = "OtterworksTest123!";

export interface Session {
  email: string;
  password: string;
  id: string;
  accessToken: string;
  refreshToken: string;
}

export function freshUserDataDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "otter-desktop-e2e-"));
}

export async function freePort(): Promise<number> {
  return new Promise((resolve) => {
    const s = net.createServer().listen(0, "127.0.0.1", () => {
      const { port } = s.address() as net.AddressInfo;
      s.close(() => resolve(port));
    });
  });
}

export function desktopEnv(extra: Record<string, string> = {}): Record<string, string> {
  const env: Record<string, string> = {};
  for (const [k, v] of Object.entries(process.env)) if (v !== undefined) env[k] = v;
  delete env.ELECTRON_RUN_AS_NODE;
  env.DISPLAY = env.DISPLAY || ":0";
  return { ...env, ...extra };
}

export interface LaunchOptions {
  userDataDir?: string;
  port?: number;
  env?: Record<string, string>;
  args?: string[];
}

export async function launchDesktop(
  opts: LaunchOptions = {}
): Promise<{ app: ElectronApplication; win: Page; userDataDir: string; port: number }> {
  const userDataDir = opts.userDataDir ?? freshUserDataDir();
  const port = opts.port ?? (await freePort());
  const app = await _electron.launch({
    executablePath: ELECTRON_BIN,
    args: [DESKTOP_DIR, `--user-data-dir=${userDataDir}`, ...(opts.args ?? [])],
    cwd: DESKTOP_DIR,
    env: desktopEnv({ OTTER_DESKTOP_PORT: String(port), ...(opts.env ?? {}) }),
  });
  const win = await app.firstWindow();
  await win.waitForLoadState("domcontentloaded");
  return { app, win, userDataDir, port };
}

export function appUrl(win: Page, pathname: string): string {
  return new URL(pathname, win.url()).toString();
}

async function gatewayJson(method: string, route: string, token?: string, body?: unknown) {
  const res = await fetch(`${GATEWAY_URL}${route}`, {
    method,
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  return { status: res.status, json: text ? JSON.parse(text) : null };
}

export async function registerViaGateway(prefix = "desktop-e2e"): Promise<Session> {
  const email = `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.test`;
  const { status, json } = await gatewayJson("POST", "/api/v1/auth/register", undefined, {
    email,
    password: TEST_PASSWORD,
    displayName: "Desktop QA",
  });
  if (status !== 201) throw new Error(`register failed: ${status} ${JSON.stringify(json)}`);
  return {
    email,
    password: TEST_PASSWORD,
    id: json.user.id,
    accessToken: json.accessToken,
    refreshToken: json.refreshToken,
  };
}

export async function createDocument(s: Session, title: string, content: string) {
  const { status, json } = await gatewayJson("POST", "/api/v1/documents/", s.accessToken, { title, content });
  if (status !== 201) throw new Error(`create document failed: ${status}`);
  return json as { id: string; title: string };
}

export async function getDocument(s: Session, id: string) {
  return (await gatewayJson("GET", `/api/v1/documents/${id}`, s.accessToken)).json as {
    title: string;
    content: string;
  };
}

export async function createFolder(s: Session, name: string) {
  const { status, json } = await gatewayJson("POST", "/api/v1/folders", s.accessToken, {
    name,
    owner_id: s.id,
  });
  if (status !== 201) throw new Error(`create folder failed: ${status}`);
  return json as { id: string; name: string };
}

export async function uploadFile(s: Session, name: string, body: string, folderId?: string) {
  const form = new FormData();
  form.append("file", new Blob([body], { type: "text/plain" }), name);
  form.append("owner_id", s.id);
  if (folderId) form.append("folder_id", folderId);
  const res = await fetch(`${GATEWAY_URL}/api/v1/files/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${s.accessToken}` },
    body: form,
  });
  if (res.status !== 201) throw new Error(`upload failed: ${res.status} ${await res.text()}`);
  return (await res.json()).file as { id: string; name: string };
}

export async function signInWithTokens(win: Page, s: Session): Promise<void> {
  await win.evaluate(
    ([a, r]) => {
      localStorage.setItem("otter_access_token", a);
      localStorage.setItem("otter_refresh_token", r);
    },
    [s.accessToken, s.refreshToken]
  );
}

/**
 * TCP forwarder in front of the API gateway that can be switched off and on, so a
 * test can take the desktop app's backend "offline" and bring it back without
 * touching the shared stack.
 */
export class ToggleableGateway {
  private server: net.Server;
  private sockets = new Set<net.Socket>();
  online = true;
  port = 0;

  constructor(private target = new URL(GATEWAY_URL)) {
    this.server = net.createServer((client) => {
      if (!this.online) {
        client.destroy();
        return;
      }
      const upstream = net.connect(Number(this.target.port || 80), this.target.hostname);
      for (const s of [client, upstream]) {
        this.sockets.add(s);
        s.on("close", () => this.sockets.delete(s));
        s.on("error", () => {
          client.destroy();
          upstream.destroy();
        });
      }
      client.pipe(upstream).pipe(client);
    });
  }

  get url(): string {
    return `http://127.0.0.1:${this.port}`;
  }

  async start(): Promise<void> {
    await new Promise<void>((r) => this.server.listen(0, "127.0.0.1", r));
    this.port = (this.server.address() as net.AddressInfo).port;
  }

  goOffline(): void {
    this.online = false;
    for (const s of this.sockets) s.destroy();
  }

  goOnline(): void {
    this.online = true;
  }

  async stop(): Promise<void> {
    this.goOffline();
    await new Promise<void>((r) => this.server.close(() => r()));
  }
}
