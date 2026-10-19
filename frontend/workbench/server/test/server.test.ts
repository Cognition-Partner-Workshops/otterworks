// @vitest-environment node
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import express from "express";
import request from "supertest";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createApp, MemoryStore, readConfig, safeReturnTo, userKey, type ServerConfig } from "../index.js";
import { createFakeIdp } from "../dev/fake-idp.js";

let idpServer: Server;
let issuer: string;
let idpApp: express.Express;

function config(overrides: Partial<ServerConfig> = {}) {
  return {
    auth: "oidc" as const,
    issuer,
    clientId: "workbench-local",
    clientSecret: "local-secret",
    publicUrl: "http://workbench.test",
    sessionSecret: "test-session-secret",
    store: "memory" as const,
    table: "workbench-attendee-state",
    port: 3002,
    distDir: "/missing-workbench-dist",
    ...overrides,
  };
}

async function signIn(agent: ReturnType<typeof request.agent>, name: string, email: string) {
  const login = await agent.get("/auth/login?returnTo=%2Fboards%2FOW%2FOW-42").expect(302);
  const authorization = new URL(login.headers.location);
  const form = await request(idpApp)
    .get(`${authorization.pathname}${authorization.search}`)
    .expect(200);
  const authorizationId = form.text.match(/name="authorization_id" value="([^"]+)"/)?.[1];
  expect(authorizationId).toBeTruthy();
  const providerResponse = await request(idpApp)
    .post("/authorize")
    .type("form")
    .send({ authorization_id: authorizationId, name, email })
    .expect(302);
  const callback = new URL(providerResponse.headers.location);
  await agent.get(`${callback.pathname}${callback.search}`).expect(302).expect("Location", "/boards/OW/OW-42");
}

beforeAll(async () => {
  const fakeIdp = await createFakeIdp();
  idpApp = fakeIdp.app;
  idpServer = createServer(idpApp);
  await new Promise<void>((resolve) => idpServer.listen(0, resolve));
  issuer = `http://127.0.0.1:${(idpServer.address() as AddressInfo).port}`;
});

afterAll(async () => {
  await new Promise<void>((resolve, reject) => idpServer.close((error) => error ? reject(error) : resolve()));
});

describe("workbench server", () => {
  it("requires authentication for API routes and redirects deep HTML navigation", async () => {
    const app = createApp(config(), new MemoryStore());
    await request(app).get("/api/me").expect(401);
    const response = await request(app).get("/boards/OW/OW-42?view=history").set("Accept", "text/html").expect(302);
    expect(response.headers.location).toBe("/auth/login?returnTo=%2Fboards%2FOW%2FOW-42%3Fview%3Dhistory");
  });

  it("uses the fixed local identity when OIDC is disabled", async () => {
    const app = createApp(config({ auth: "none", clientId: undefined, clientSecret: undefined }), new MemoryStore());
    const response = await request(app).get("/api/me").expect(200, {
      sub: "local",
      name: "Local user",
      email: "local@example.com",
    });
    expect(response.headers["cache-control"]).toBe("no-store");
  });

  it("starts a PKCE S256 authorization request and completes the signed callback", async () => {
    const agent = request.agent(createApp(config(), new MemoryStore()));
    const login = await agent.get("/auth/login?returnTo=%2Fboards%2FOW%2FOW-42").expect(302);
    const authorization = new URL(login.headers.location);
    expect(authorization.searchParams.get("code_challenge_method")).toBe("S256");
    expect(authorization.searchParams.get("code_challenge")).toBeTruthy();
    expect(authorization.searchParams.get("state")).toBeTruthy();
    expect(authorization.searchParams.get("scope")).toBe("openid profile email");

    const idpUrl = new URL(login.headers.location);
    const form = await request(idpApp).get(`${idpUrl.pathname}${idpUrl.search}`).expect(200);
    const authorizationId = form.text.match(/name="authorization_id" value="([^"]+)"/)?.[1];
    expect(authorizationId).toBeTruthy();
    const providerResponse = await request(idpApp).post("/authorize").type("form").send({
      authorization_id: authorizationId,
      name: "Alice Example",
      email: "alice@example.com",
    }).expect(302);
    const callback = new URL(providerResponse.headers.location);
    await agent.get(`${callback.pathname}${callback.search}`).expect(302).expect("Location", "/boards/OW/OW-42");
    await agent.get("/api/me").expect(200, {
      sub: "alice",
      name: "Alice Example",
      email: "alice@example.com",
    });
  });

  it("keeps authorization parameters server-side while rendering the fake IdP form", async () => {
    const response = await request(idpApp).get("/authorize").query({
      redirect_uri: "https://client.example.test/auth/callback",
      state: "form-state",
      nonce: "form-nonce",
      code_challenge: "form-challenge",
      code_challenge_method: "S256",
      name: "Query Attendee",
      email: "query@example.com",
    }).expect(200);
    expect(response.text).not.toContain("https://client.example.test/auth/callback");
    const authorizationId = response.text.match(/name="authorization_id" value="([^"]+)"/)?.[1];
    expect(authorizationId).toBeTruthy();

    const completed = await request(idpApp).post("/authorize").type("form").send({
      authorization_id: authorizationId,
      name: "Local attendee",
      email: "attendee@example.com",
    }).expect(302);
    const callback = new URL(completed.headers.location);
    expect(callback.origin + callback.pathname).toBe("https://client.example.test/auth/callback");
    expect(callback.searchParams.get("state")).toBe("form-state");
  });

  it("rate limits the fake IdP authorize and token endpoints", async () => {
    const limitedIdp = await createFakeIdp({ rateLimit: 1 });
    await request(limitedIdp.app).get("/authorize").expect(400);
    await request(limitedIdp.app).get("/authorize").expect(429);
    await request(limitedIdp.app).post("/token").type("form").send({
      code: "invalid",
      grant_type: "authorization_code",
    }).expect(400);
    await request(limitedIdp.app).post("/token").type("form").send({
      code: "invalid",
      grant_type: "authorization_code",
    }).expect(429);
  });

  it("sets a secure session cookie behind the trusted TLS proxy", async () => {
    const app = createApp(config({ publicUrl: "https://workbench.example.test" }), new MemoryStore());
    const response = await request(app)
      .get("/auth/login")
      .set("X-Forwarded-Proto", "https")
      .expect(302);
    expect(response.headers["set-cookie"]).toEqual(expect.arrayContaining([
      expect.stringMatching(/\bsecure\b/i),
    ]));
  });

  it("requires an OIDC session secret and keeps a default only for no-auth mode", async () => {
    expect(readConfig({ WORKBENCH_AUTH: "oidc" }).sessionSecret).toBeUndefined();
    expect(readConfig({ WORKBENCH_AUTH: "oidc", SESSION_SECRET: "" }).sessionSecret).toBeUndefined();
    expect(readConfig({ WORKBENCH_AUTH: "none" }).sessionSecret).toBe("local-workbench-session-secret");
    expect(readConfig({ WORKBENCH_AUTH: "none", SESSION_SECRET: "" }).sessionSecret).toBe("local-workbench-session-secret");

    const app = createApp(config({ sessionSecret: undefined }), new MemoryStore());
    await request(app).get("/").set("Accept", "text/html").expect(503)
      .expect(/Sign-in is not configured yet/);
  });

  it("shows a retry link with the saved destination when the provider denies sign-in", async () => {
    const agent = request.agent(createApp(config(), new MemoryStore()));
    const login = await agent.get("/auth/login?returnTo=%2Fboards%2FOW%2FOW-42").expect(302);
    const state = new URL(login.headers.location).searchParams.get("state");
    const response = await agent.get("/auth/callback")
      .query({ error: "access_denied", state })
      .expect(400);
    expect(response.text).toContain("Sign-in did not complete");
    expect(response.text).toContain('href="/auth/login?returnTo=%2Fboards%2FOW%2FOW-42">Try again</a>');
  });

  it("rejects bad state and unsafe return destinations", async () => {
    const agent = request.agent(createApp(config(), new MemoryStore()));
    await agent.get("/auth/callback?state=wrong&code=unused").expect(400);
    expect(safeReturnTo("//evil.example", "https://workbench.test")).toBe("/");
    expect(safeReturnTo("https://evil.example", "https://workbench.test")).toBe("/");
    expect(safeReturnTo("/\\evil.example", "https://workbench.test")).toBe("/");
    expect(safeReturnTo("/boards/OW/OW-42?tab=history#comments", "https://workbench.test"))
      .toBe("/boards/OW/OW-42?tab=history#comments");
    expect(safeReturnTo("https://workbench.test/boards/OW/OW-42?tab=history", "https://workbench.test"))
      .toBe("/boards/OW/OW-42?tab=history");
  });

  it("isolates attendee state and resets only the caller", async () => {
    const store = new MemoryStore();
    const app = createApp(config(), store);
    const alice = request.agent(app);
    const bob = request.agent(app);
    await signIn(alice, "Alice Example", "alice@example.com");
    await signIn(bob, "Bob Example", "bob@example.com");

    await alice.put("/api/state/chat").set("X-Workbench-Request", "1").send([{ id: "alice-message" }]).expect(204);
    await bob.put("/api/state/chat").set("X-Workbench-Request", "1").send([{ id: "bob-message" }]).expect(204);
    await alice.get("/api/state").expect(200, {
      boards: null,
      chat: [{ id: "alice-message" }],
      settings: null,
    });
    await bob.get("/api/state").expect(200, {
      boards: null,
      chat: [{ id: "bob-message" }],
      settings: null,
    });
    await alice.delete("/api/state").set("X-Workbench-Request", "1").expect(204);
    await alice.get("/api/state").expect(200, { boards: null, chat: null, settings: null });
    await bob.get("/api/state").expect(200, {
      boards: null,
      chat: [{ id: "bob-message" }],
      settings: null,
    });
    expect(userKey("alice#one")).toBe("fk:alice_one");
  });

  it("requires the custom request header and a same-origin Origin for API writes", async () => {
    const agent = request.agent(createApp(config(), new MemoryStore()));
    await signIn(agent, "Alice Example", "alice@example.com");

    await agent.put("/api/state/chat").send([]).expect(403);
    await agent.put("/api/state/chat")
      .set("X-Workbench-Request", "1")
      .set("Origin", "https://foreign.example")
      .send([])
      .expect(403);
    await agent.put("/api/state/chat")
      .set("X-Workbench-Request", "1")
      .set("Origin", "http://workbench.test")
      .send([])
      .expect(204);
  });

  it("limits auth requests per IP and API requests per session subject", async () => {
    const authApp = createApp(config({ auth: "none", authRateLimit: 2 }), new MemoryStore());
    await request(authApp).get("/auth/login").expect(302);
    await request(authApp).get("/auth/login").expect(302);
    await request(authApp).get("/auth/login").expect(429);

    const apiApp = createApp(config({ apiRateLimit: 1 }), new MemoryStore());
    await request(apiApp).get("/api/me").expect(401);
    await request(apiApp).get("/api/me").expect(429);

    const userApp = createApp(config({ apiRateLimit: 1 }), new MemoryStore());
    const alice = request.agent(userApp);
    const bob = request.agent(userApp);
    await signIn(alice, "Alice Example", "alice@example.com");
    await signIn(bob, "Bob Example", "bob@example.com");
    await alice.get("/api/me").expect(200);
    await alice.get("/api/state").expect(429);
    await bob.get("/api/me").expect(200);
  });

  it("serves health while sign-in configuration is missing and returns a 503 HTML page", async () => {
    const app = createApp(config({ clientId: undefined, clientSecret: undefined }), new MemoryStore());
    await request(app).get("/healthz").expect(200, "ok");
    await request(app).get("/").set("Accept", "text/html").expect(503).expect(/Sign-in is not configured yet/);
    await request(app).get("/signed-out").expect(503).expect(/Sign-in is not configured yet/);
  });
});
