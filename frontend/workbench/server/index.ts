import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DeleteCommand, DynamoDBDocumentClient, PutCommand, QueryCommand } from "@aws-sdk/lib-dynamodb";
import cookieSession from "cookie-session";
import express, { type NextFunction, type Request, type Response } from "express";
import { rateLimit } from "express-rate-limit";
import { generators, Issuer, type Client } from "openid-client";
import path from "node:path";

const THIRTY_DAYS = 30 * 24 * 60 * 60;
const SESSION_TTL_MS = 12 * 60 * 60 * 1000;
const MAX_STATE_BYTES = 350 * 1024;
const DOCS = ["boards", "chat", "settings"] as const;
type StateDoc = typeof DOCS[number];

export interface User {
  sub: string;
  name: string;
  email: string;
}

export interface StateStore {
  get(userKey: string): Promise<Partial<Record<StateDoc, unknown>>>;
  put(userKey: string, doc: StateDoc, value: unknown): Promise<void>;
  reset(userKey: string): Promise<void>;
}

export interface ServerConfig {
  auth: "oidc" | "none";
  issuer: string;
  clientId?: string;
  clientSecret?: string;
  publicUrl: string;
  sessionSecret?: string;
  store: "dynamodb" | "memory";
  table: string;
  region?: string;
  port: number;
  distDir: string;
  authRateLimit?: number;
  apiRateLimit?: number;
}

export function readConfig(env: NodeJS.ProcessEnv = process.env): ServerConfig {
  const auth = env.WORKBENCH_AUTH === "none" ? "none" : "oidc";
  const publicUrl = env.WORKBENCH_PUBLIC_URL ?? "http://localhost:3002";
  return {
    auth,
    issuer: env.OIDC_ISSUER ?? "https://fieldkit.devin.ai",
    clientId: env.OIDC_CLIENT_ID,
    clientSecret: env.OIDC_CLIENT_SECRET,
    publicUrl,
    sessionSecret: env.SESSION_SECRET || (auth === "none" ? "local-workbench-session-secret" : undefined),
    store: env.WORKBENCH_STORE === "memory" ? "memory" : "dynamodb",
    table: env.WORKBENCH_TABLE ?? "workbench-attendee-state",
    region: env.AWS_REGION,
    port: Number(env.PORT ?? 3002),
    distDir: path.resolve(process.cwd(), "dist"),
  };
}

export function safeReturnTo(value: unknown, publicOrigin: string): string {
  if (typeof value !== "string") return "/";
  try {
    const origin = new URL(publicOrigin).origin;
    const url = new URL(value, origin);
    return url.origin === origin ? `${url.pathname}${url.search}${url.hash}` : "/";
  } catch {
    return "/";
  }
}

export function userKey(sub: string): string {
  return `fk:${sub.replace(/#/g, "_")}`;
}

export class MemoryStore implements StateStore {
  private readonly data = new Map<string, Partial<Record<StateDoc, unknown>>>();

  async get(key: string): Promise<Partial<Record<StateDoc, unknown>>> {
    return { ...(this.data.get(key) ?? {}) };
  }

  async put(key: string, doc: StateDoc, value: unknown): Promise<void> {
    const state = { ...(this.data.get(key) ?? {}) };
    assignStateDoc(state, doc, value);
    this.data.set(key, state);
  }

  async reset(key: string): Promise<void> {
    this.data.delete(key);
  }
}

function assignStateDoc(state: Partial<Record<StateDoc, unknown>>, doc: string, value: unknown): void {
  switch (doc) {
    case "boards":
      state.boards = value;
      break;
    case "chat":
      state.chat = value;
      break;
    case "settings":
      state.settings = value;
      break;
  }
}

function isStateDoc(doc: string): doc is StateDoc {
  return DOCS.some((allowedDoc) => allowedDoc === doc);
}

export class DynamoStore implements StateStore {
  private readonly client: DynamoDBDocumentClient;

  constructor(private readonly table: string, region?: string) {
    this.client = DynamoDBDocumentClient.from(new DynamoDBClient({ region }), {
      marshallOptions: { removeUndefinedValues: true },
    });
  }

  async get(key: string): Promise<Partial<Record<StateDoc, unknown>>> {
    const state: Partial<Record<StateDoc, unknown>> = {};
    let lastKey: Record<string, unknown> | undefined;
    do {
      const response = await this.client.send(new QueryCommand({
        TableName: this.table,
        KeyConditionExpression: "#user = :user",
        ExpressionAttributeNames: { "#user": "user" },
        ExpressionAttributeValues: { ":user": key },
        ...(lastKey ? { ExclusiveStartKey: lastKey } : {}),
      }));
      for (const item of response.Items ?? []) {
        if (typeof item.doc !== "string" || typeof item.value !== "string") continue;
        try {
          assignStateDoc(state, item.doc, JSON.parse(item.value));
        } catch {
          continue;
        }
      }
      lastKey = response.LastEvaluatedKey;
    } while (lastKey);
    return state;
  }

  async put(key: string, doc: StateDoc, value: unknown): Promise<void> {
    await this.client.send(new PutCommand({
      TableName: this.table,
      Item: {
        user: key,
        doc,
        value: JSON.stringify(value),
        updated_at: new Date().toISOString(),
        expires_at: Math.floor(Date.now() / 1000) + THIRTY_DAYS,
      },
    }));
  }

  async reset(key: string): Promise<void> {
    let lastKey: Record<string, unknown> | undefined;
    do {
      const response = await this.client.send(new QueryCommand({
        TableName: this.table,
        KeyConditionExpression: "#user = :user",
        ExpressionAttributeValues: { ":user": key },
        ProjectionExpression: "#user, #doc",
        ExpressionAttributeNames: { "#user": "user", "#doc": "doc" },
        ...(lastKey ? { ExclusiveStartKey: lastKey } : {}),
      }));
      await Promise.all((response.Items ?? []).map((item) => this.client.send(new DeleteCommand({
        TableName: this.table,
        Key: { user: item.user, doc: item.doc },
      }))));
      lastKey = response.LastEvaluatedKey;
    } while (lastKey);
  }
}

type SessionState = {
  user?: User;
  issuedAt?: number;
  authRequest?: { state: string; nonce: string; codeVerifier: string; returnTo: string; expiresAt: number };
};

let discovery: { issuer: string; client: Promise<Client> } | undefined;

async function getClient(config: ServerConfig): Promise<Client> {
  if (!discovery || discovery.issuer !== config.issuer) {
    discovery = {
      issuer: config.issuer,
      client: Issuer.discover(config.issuer).then((issuer) => new issuer.Client({
        client_id: config.clientId!,
        client_secret: config.clientSecret!,
        redirect_uris: [`${config.publicUrl.replace(/\/$/, "")}/auth/callback`],
        response_types: ["code"],
        token_endpoint_auth_method: "client_secret_post",
      })),
    };
  }
  return discovery.client;
}

function currentUser(req: Request): User | undefined {
  return (req.session as SessionState | null)?.user;
}

function csrfProtection(publicOrigin: string) {
  return (req: Request, res: Response, next: NextFunction) => {
    if (req.method === "GET" || req.method === "HEAD") {
      next();
      return;
    }
    const origin = req.get("Origin");
    if (req.get("X-Workbench-Request") !== "1" || (origin !== undefined && origin !== publicOrigin)) {
      res.status(403).json({ error: "forbidden" });
      return;
    }
    next();
  };
}

function userFromClaims(claims: Record<string, unknown>, fallback?: Record<string, unknown>): User {
  const source = { ...fallback, ...claims };
  const sub = typeof source.sub === "string" ? source.sub : "";
  if (!sub) throw new Error("Identity provider returned no subject");
  return {
    sub,
    name: typeof source.name === "string" ? source.name : "Workbench attendee",
    email: typeof source.email === "string" ? source.email : "",
  };
}

function sendPage(res: Response, title: string, body: string, status = 200): void {
  res.status(status).type("html").send(
    `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${title}</title><main><h1>${title}</h1>${body}</main></html>`,
  );
}

export function createApp(config = readConfig(), store: StateStore = config.store === "memory"
  ? new MemoryStore()
  : new DynamoStore(config.table, config.region)) {
  const app = express();
  const publicOrigin = new URL(config.publicUrl).origin;
  const sessionSecret = config.sessionSecret || (config.auth === "none" ? "local-workbench-session-secret" : undefined);
  const configured = config.auth === "none" || Boolean(config.clientId && config.clientSecret && sessionSecret);

  app.set("trust proxy", 1);
  app.disable("x-powered-by");
  app.use((_req: Request, res: Response, next: NextFunction) => {
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("X-Frame-Options", "DENY");
    res.setHeader("Content-Security-Policy", "frame-ancestors 'none'");
    res.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
    next();
  });
  if (sessionSecret) {
    app.use(cookieSession({
      name: "workbench_session",
      keys: [sessionSecret],
      maxAge: SESSION_TTL_MS,
      httpOnly: true,
      secure: config.publicUrl.startsWith("https://"),
      sameSite: "lax",
    }));
  }
  app.use("/auth", rateLimit({
    windowMs: 5 * 60 * 1000,
    limit: config.authRateLimit ?? 300,
    standardHeaders: true,
    legacyHeaders: false,
  }));
  app.use("/api", rateLimit({
    windowMs: 60 * 1000,
    limit: config.apiRateLimit ?? 1200,
    standardHeaders: true,
    legacyHeaders: false,
    keyGenerator: (req) => {
      const user = currentUser(req);
      return user ? `sub:${user.sub}` : `ip:${req.ip}`;
    },
  }));
  app.use("/api", csrfProtection(publicOrigin));
  app.use("/auth", csrfProtection(publicOrigin));
  app.use(express.json({
    limit: "350kb",
    verify: (req, _res, buffer) => {
      if (buffer.length > MAX_STATE_BYTES) throw Object.assign(new Error("Request body is too large"), { status: 413 });
      (req as Request & { rawBody?: Buffer }).rawBody = buffer;
    },
  }));
  app.use(express.urlencoded({ extended: false }));

  app.get("/healthz", (_req, res) => res.status(200).type("text").send("ok"));
  app.get("/signed-out", (_req, res) => {
    if (!configured) {
      sendPage(res, "Sign-in is not configured yet", "<p>Sign-in is not configured yet.</p>", 503);
      return;
    }
    sendPage(res, "Signed out", '<p>You have been signed out.</p><p><a href="/auth/login">Sign in again</a></p>');
  });

  app.get("/auth/login", async (req, res, next) => {
    if (!configured) {
      sendPage(res, "Sign-in is not configured yet", "<p>Sign-in is not configured yet.</p>", 503);
      return;
    }
    if (config.auth === "none") {
      req.session = { user: { sub: "local", name: "Local user", email: "local@example.com" } } as SessionState;
      res.redirect(safeReturnTo(req.query.returnTo, publicOrigin));
      return;
    }
    try {
      const client = await getClient(config);
      const codeVerifier = generators.codeVerifier();
      const state = generators.state();
      const nonce = generators.nonce();
      const codeChallenge = generators.codeChallenge(codeVerifier);
      (req.session as SessionState).authRequest = {
        state,
        nonce,
        codeVerifier,
        returnTo: safeReturnTo(req.query.returnTo, publicOrigin),
        expiresAt: Date.now() + 5 * 60 * 1000,
      };
      res.redirect(client.authorizationUrl({
        scope: "openid profile email",
        code_challenge: codeChallenge,
        code_challenge_method: "S256",
        state,
        nonce,
      }));
    } catch (error) {
      next(error);
    }
  });

  app.get("/auth/callback", async (req, res) => {
    if (!configured) {
      sendPage(res, "Sign-in is not configured yet", "<p>Sign-in is not configured yet.</p>", 503);
      return;
    }
    const authRequest = (req.session as SessionState | null)?.authRequest;
    if (!authRequest || authRequest.expiresAt < Date.now() || req.query.state !== authRequest.state) {
      res.status(400).type("text").send("Invalid sign-in state");
      return;
    }
    if (typeof req.query.error === "string") {
      const loginUrl = `/auth/login?returnTo=${encodeURIComponent(authRequest.returnTo)}`;
      sendPage(res, "Sign-in did not complete", `<p>Sign-in did not complete.</p><p><a href="${loginUrl}">Try again</a></p>`, 400);
      return;
    }
    try {
      const client = await getClient(config);
      const tokens = await client.callback(
        `${config.publicUrl.replace(/\/$/, "")}/auth/callback`,
        client.callbackParams(req),
        { state: authRequest.state, nonce: authRequest.nonce, code_verifier: authRequest.codeVerifier },
      );
      const claims = tokens.claims() as Record<string, unknown>;
      let userInfo: Record<string, unknown> | undefined;
      if (typeof claims.name !== "string" || typeof claims.email !== "string") {
        userInfo = await client.userinfo(tokens.access_token!) as Record<string, unknown>;
      }
      const user = userFromClaims(claims, userInfo);
      req.session = { user, issuedAt: Date.now() } as SessionState;
      res.redirect(authRequest.returnTo);
    } catch {
      const loginUrl = `/auth/login?returnTo=${encodeURIComponent(authRequest.returnTo)}`;
      sendPage(res, "Sign-in did not complete", `<p>Sign-in did not complete.</p><p><a href="${loginUrl}">Try again</a></p>`, 400);
    }
  });

  app.get("/auth/logout", (req, res) => {
    if (!configured) {
      sendPage(res, "Sign-in is not configured yet", "<p>Sign-in is not configured yet.</p>", 503);
      return;
    }
    req.session = null;
    res.redirect("/signed-out");
  });

  const requireUser = (req: Request, res: Response, next: NextFunction) => {
    if (!currentUser(req) && config.auth === "none") {
      (req.session as SessionState).user = { sub: "local", name: "Local user", email: "local@example.com" };
    }
    if (!currentUser(req)) {
      res.status(401).json({ error: "unauthorized" });
      return;
    }
    next();
  };

  app.use("/api", requireUser);
  app.get("/api/me", (req, res) => res.json(currentUser(req)));
  app.get("/api/state", async (req, res, next) => {
    try {
      const state = await store.get(userKey(currentUser(req)!.sub));
      res.json({
        boards: state.boards ?? null,
        chat: state.chat ?? null,
        settings: state.settings ?? null,
      });
    } catch (error) {
      next(error);
    }
  });
  app.put("/api/state/:doc", async (req, res, next) => {
    const doc = req.params.doc;
    if (!isStateDoc(doc)) {
      res.status(400).json({ error: "invalid document" });
      return;
    }
    if (!req.is("application/json")) {
      res.status(415).json({ error: "application/json required" });
      return;
    }
    try {
      await store.put(userKey(currentUser(req)!.sub), doc, req.body);
      res.status(204).end();
    } catch (error) {
      next(error);
    }
  });
  app.delete("/api/state", async (req, res, next) => {
    try {
      await store.reset(userKey(currentUser(req)!.sub));
      res.status(204).end();
    } catch (error) {
      next(error);
    }
  });

  app.use("/assets", express.static(path.join(config.distDir, "assets"), {
    immutable: true,
    maxAge: "1y",
    fallthrough: true,
  }));
  app.get("*", (req, res, next) => {
    if (req.path === "/api" || req.path.startsWith("/api/") || req.path === "/auth" || req.path.startsWith("/auth/")) {
      res.status(404).end();
      return;
    }
    if (!configured) {
      sendPage(res, "Sign-in is not configured yet", "<p>Sign-in is not configured yet.</p>", 503);
      return;
    }
    if (!currentUser(req) && config.auth === "none") {
      (req.session as SessionState).user = { sub: "local", name: "Local user", email: "local@example.com" };
    }
    if (!currentUser(req)) {
      const isHtmlNavigation = req.accepts("html") || req.get("sec-fetch-dest") === "document";
      if (!isHtmlNavigation) {
        res.status(401).type("text").send("Sign-in required");
        return;
      }
      res.redirect(`/auth/login?returnTo=${encodeURIComponent(`${req.originalUrl}`)}`);
      return;
    }
    res.sendFile(path.join(config.distDir, "index.html"), (error) => {
      if (error) next(error);
    });
  });

  app.use((error: Error & { status?: number }, _req: Request, res: Response, _next: NextFunction) => {
    if (res.headersSent) return;
    const status = error.status === 413 ? 413 : 500;
    res.status(status).type("text").send(status === 413 ? "Request body is too large" : "Workbench request failed");
  });
  return app;
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname)) {
  const config = readConfig();
  createApp(config).listen(config.port, () => {
    process.stdout.write(`Workbench listening on ${config.port}\n`);
  });
}
