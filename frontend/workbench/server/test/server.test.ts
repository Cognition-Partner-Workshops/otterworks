// @vitest-environment node
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import express from "express";
import request from "supertest";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createApp, MemoryStore, safeReturnTo, userKey, type ServerConfig } from "../index.js";
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
  authorization.searchParams.set("name", name);
  authorization.searchParams.set("email", email);
  const providerResponse = await request(idpApp)
    .get(`${authorization.pathname}${authorization.search}`)
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
    idpUrl.searchParams.set("name", "Alice Example");
    idpUrl.searchParams.set("email", "alice@example.com");
    const providerResponse = await request(idpApp).get(`${idpUrl.pathname}${idpUrl.search}`).expect(302);
    const callback = new URL(providerResponse.headers.location);
    await agent.get(`${callback.pathname}${callback.search}`).expect(302).expect("Location", "/boards/OW/OW-42");
    await agent.get("/api/me").expect(200, {
      sub: "alice",
      name: "Alice Example",
      email: "alice@example.com",
    });
  });

  it("rejects bad state and unsafe return destinations", async () => {
    const agent = request.agent(createApp(config(), new MemoryStore()));
    await agent.get("/auth/callback?state=wrong&code=unused").expect(400);
    expect(safeReturnTo("//evil.example")).toBe("/");
    expect(safeReturnTo("https://evil.example")).toBe("/");
    expect(safeReturnTo("/\\evil.example")).toBe("/");
    expect(safeReturnTo("/boards/OW/OW-42?tab=history")).toBe("/boards/OW/OW-42?tab=history");
  });

  it("isolates attendee state and resets only the caller", async () => {
    const store = new MemoryStore();
    const app = createApp(config(), store);
    const alice = request.agent(app);
    const bob = request.agent(app);
    await signIn(alice, "Alice Example", "alice@example.com");
    await signIn(bob, "Bob Example", "bob@example.com");

    await alice.put("/api/state/chat").send([{ id: "alice-message" }]).expect(204);
    await bob.put("/api/state/chat").send([{ id: "bob-message" }]).expect(204);
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
    await alice.delete("/api/state").expect(204);
    await alice.get("/api/state").expect(200, { boards: null, chat: null, settings: null });
    await bob.get("/api/state").expect(200, {
      boards: null,
      chat: [{ id: "bob-message" }],
      settings: null,
    });
    expect(userKey("alice#one")).toBe("fk:alice_one");
  });

  it("serves health while sign-in configuration is missing and returns a 503 HTML page", async () => {
    const app = createApp(config({ clientId: undefined, clientSecret: undefined }), new MemoryStore());
    await request(app).get("/healthz").expect(200, "ok");
    await request(app).get("/").set("Accept", "text/html").expect(503).expect(/Sign-in is not configured yet/);
    await request(app).get("/signed-out").expect(503).expect(/Sign-in is not configured yet/);
  });
});
