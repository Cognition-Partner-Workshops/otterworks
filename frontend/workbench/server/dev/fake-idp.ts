import express, { type Request, type Response } from "express";
import { exportJWK, generateKeyPair, SignJWT } from "jose";
import { createHash, randomUUID } from "node:crypto";
import { createServer } from "node:http";

interface AuthorizationRequest {
  redirectUri: string;
  state: string;
  nonce: string;
  codeChallenge: string;
  codeChallengeMethod: string;
}

interface FakeUser {
  name: string;
  email: string;
}

export async function createFakeIdp() {
  const { privateKey, publicKey } = await generateKeyPair("RS256");
  const publicJwk = await exportJWK(publicKey);
  publicJwk.kid = "fake-idp-key";
  publicJwk.alg = "RS256";
  publicJwk.use = "sig";
  const codes = new Map<string, { request: AuthorizationRequest; user: FakeUser }>();
  const accessTokens = new Map<string, FakeUser>();
  const pendingAuthorizations = new Map<string, AuthorizationRequest>();
  const app = express();
  app.use(express.urlencoded({ extended: false }));

  const issuer = (req: Request) => `${req.protocol}://${req.get("host")}`;
  app.get("/.well-known/openid-configuration", (req, res) => {
    const base = issuer(req);
    res.json({
      issuer: base,
      authorization_endpoint: `${base}/authorize`,
      token_endpoint: `${base}/token`,
      userinfo_endpoint: `${base}/userinfo`,
      jwks_uri: `${base}/jwks`,
      response_types_supported: ["code"],
      subject_types_supported: ["public"],
      id_token_signing_alg_values_supported: ["RS256"],
      scopes_supported: ["openid", "profile", "email"],
      token_endpoint_auth_methods_supported: ["client_secret_post", "client_secret_basic"],
      claims_supported: ["sub", "name", "email", "email_verified", "preferred_username", "groups"],
      code_challenge_methods_supported: ["S256"],
    });
  });
  app.get("/jwks", (_req, res) => res.json({ keys: [publicJwk] }));
  app.get("/authorize", (req, res) => {
    const request: AuthorizationRequest = {
      redirectUri: String(req.query.redirect_uri ?? ""),
      state: String(req.query.state ?? ""),
      nonce: String(req.query.nonce ?? ""),
      codeChallenge: String(req.query.code_challenge ?? ""),
      codeChallengeMethod: String(req.query.code_challenge_method ?? ""),
    };
    if (!request.redirectUri || !request.state || !request.nonce || request.codeChallengeMethod !== "S256") {
      res.status(400).type("text").send("Invalid authorization request");
      return;
    }
    if (req.query.name && req.query.email) {
      completeAuthorization(request, { name: String(req.query.name), email: String(req.query.email) }, res);
      return;
    }
    const authorizationId = randomUUID();
    pendingAuthorizations.set(authorizationId, request);
    res.type("html").send(`<!doctype html><html lang="en"><meta charset="utf-8"><title>Local identity</title><main><h1>Local identity</h1><form method="post" action="/authorize"><input type="hidden" name="authorization_id" value="${authorizationId}"><label>Name <input name="name" required value="Local attendee"></label><label>Email <input name="email" type="email" required value="attendee@example.com"></label><button>Continue</button></form></main></html>`);
  });
  app.post("/authorize", (req, res) => {
    const authorizationId = String(req.body.authorization_id ?? "");
    const request = pendingAuthorizations.get(authorizationId);
    if (!request) {
      res.status(400).type("text").send("Invalid authorization request");
      return;
    }
    pendingAuthorizations.delete(authorizationId);
    completeAuthorization(request, {
      name: String(req.body.name ?? ""),
      email: String(req.body.email ?? ""),
    }, res);
  });
  app.post("/token", async (req, res) => {
    const entry = codes.get(String(req.body.code ?? ""));
    if (!entry || req.body.grant_type !== "authorization_code") {
      res.status(400).json({ error: "invalid_grant" });
      return;
    }
    const challenge = createHash("sha256").update(String(req.body.code_verifier ?? "")).digest("base64url");
    if (challenge !== entry.request.codeChallenge || req.body.client_id !== "workbench-local") {
      res.status(400).json({ error: "invalid_grant" });
      return;
    }
    codes.delete(String(req.body.code));
    const now = Math.floor(Date.now() / 1000);
    const accessToken = randomUUID();
    accessTokens.set(accessToken, entry.user);
    const idToken = await new SignJWT({
      name: entry.user.name,
      email: entry.user.email,
      email_verified: true,
      preferred_username: entry.user.email.split("@")[0],
      groups: [],
      nonce: entry.request.nonce,
    })
      .setProtectedHeader({ alg: "RS256", kid: "fake-idp-key" })
      .setIssuer(issuer(req))
      .setSubject(entry.user.email.split("@")[0])
      .setAudience(String(req.body.client_id ?? "workbench-local"))
      .setIssuedAt(now)
      .setExpirationTime(now + 3600)
      .sign(privateKey);
    res.json({ access_token: accessToken, token_type: "Bearer", expires_in: 3600, id_token: idToken });
  });
  app.get("/userinfo", (req, res) => {
    const authorization = req.get("authorization") ?? "";
    const user = authorization.startsWith("Bearer ") ? accessTokens.get(authorization.slice(7)) : undefined;
    if (!user) {
      res.status(401).json({ error: "invalid_token" });
      return;
    }
    res.json({ sub: user.email.split("@")[0], name: user.name, email: user.email });
  });

  function completeAuthorization(request: AuthorizationRequest, user: FakeUser, res: Response) {
    if (!request.redirectUri || !request.state || !user.name || !user.email || request.codeChallengeMethod !== "S256") {
      res.status(400).type("text").send("Invalid authorization request");
      return;
    }
    const code = randomUUID();
    codes.set(code, { request, user });
    const callback = new URL(request.redirectUri);
    callback.searchParams.set("code", code);
    callback.searchParams.set("state", request.state);
    res.redirect(callback.toString());
  }

  return { app };
}

if (process.argv[1]?.endsWith("/fake-idp.ts")) {
  void createFakeIdp().then(({ app }) => {
    const port = Number(process.env.FAKE_IDP_PORT ?? 9400);
    createServer(app).listen(port, () => process.stdout.write(`Fake identity provider listening on ${port}\n`));
  });
}
