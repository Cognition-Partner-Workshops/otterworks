// node --test tests/   (Node >= 22.18 strips the types from lib/cd.ts)
import { test } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, sign } from "node:crypto";
import {
  cdTenantIdForBranch,
  isBuildTagFor,
  parseTrustedRepos,
  verifyGithubOidc,
  OidcError,
  GITHUB_OIDC_ISSUER,
} from "../lib/cd.ts";

const PERPETUAL = new Set(["main", "cloud-worker"]);
const SHA = "0123456789abcdef0123456789abcdef01234567";

test("workshop-main and demo-main never map to the perpetual tenant", () => {
  for (const b of ["workshop-main", "demo-main", "workshop-cloud-worker"]) {
    const r = cdTenantIdForBranch(b, "", PERPETUAL);
    assert.equal(r.ok, false, b);
    assert.match(r.error, /perpetual/);
  }
});

test("branch names that do not round-trip to an id are refused", () => {
  for (const b of [
    "workshop-Main", // lowercases onto main
    "workshop-MAIN",
    "workshop-a_b", // folds onto a-b
    "workshop-a--b",
    "workshop--main",
    "workshop-main-",
    "workshop-",
    "workshop/main",
    "demo-main.x",
    `workshop-${"a".repeat(41)}`, // truncates
    "main",
    "feature-x",
  ]) {
    assert.equal(cdTenantIdForBranch(b, "", PERPETUAL).ok, false, b);
  }
});

test("valid branches map to exactly the id they spell, prefix included", () => {
  assert.deepEqual(cdTenantIdForBranch("workshop-alice", "", PERPETUAL), { ok: true, value: "alice" });
  assert.deepEqual(cdTenantIdForBranch("demo-retail-2", "", PERPETUAL), { ok: true, value: "retail-2" });
  assert.deepEqual(cdTenantIdForBranch("demo-main", "gtm", PERPETUAL), { ok: true, value: "gtm-main" });
  assert.equal(cdTenantIdForBranch(`demo-${"a".repeat(36)}`, "gtm", PERPETUAL).ok, true); // 40 chars
  assert.equal(cdTenantIdForBranch(`demo-${"a".repeat(37)}`, "gtm", PERPETUAL).ok, false); // 41
});

test("only this commit's immutable build tag is deployable", () => {
  assert.ok(isBuildTagFor("workshop-alice-0123456", "workshop-alice", SHA, ""));
  assert.ok(isBuildTagFor("gtm-demo-x-0123456", "demo-x", SHA, "gtm"));
  for (const t of ["main", "tenant-main", "tenant-alice", "demo-alice-0123456", "workshop-alice-fffffff", "workshop-alice-0123456-r2", ""]) {
    assert.equal(isBuildTagFor(t, "workshop-alice", SHA, ""), false, t);
  }
  assert.equal(isBuildTagFor("workshop-alice-0123456", "workshop-alice", "nothex", ""), false);
});

test("trusted repos parse case-insensitively with their prefix", () => {
  const m = parseTrustedRepos("Cognition-Partner-Workshops/otterworks=, COG-GTM/otterworks=gtm,,");
  assert.equal(m.get("cognition-partner-workshops/otterworks"), "");
  assert.equal(m.get("cog-gtm/otterworks"), "gtm");
  assert.equal(m.get("someone/else"), undefined);
});

// ---- OIDC verification ----
const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const other = generateKeyPairSync("rsa", { modulusLength: 2048 });
const jwk = publicKey.export({ format: "jwk" });
const getKey = async (kid) => (kid === "k1" ? jwk : undefined);
const now = 1_800_000_000;
const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
function mint(claims = {}, { key = privateKey, header = {} } = {}) {
  const h = b64({ alg: "RS256", kid: "k1", typ: "JWT", ...header });
  const p = b64({
    iss: GITHUB_OIDC_ISSUER,
    aud: "otterworks-demo-ops",
    sub: "repo:Cognition-Partner-Workshops/otterworks:ref:refs/heads/workshop-alice",
    repository: "Cognition-Partner-Workshops/otterworks",
    ref: "refs/heads/workshop-alice",
    ref_type: "branch",
    sha: SHA,
    event_name: "push",
    exp: now + 300,
    nbf: now - 10,
    ...claims,
  });
  const s = sign("RSA-SHA256", Buffer.from(`${h}.${p}`), key).toString("base64url");
  return `${h}.${p}.${s}`;
}
const opts = { audience: "otterworks-demo-ops", getKey, now };

test("a genuine push token verifies", async () => {
  const c = await verifyGithubOidc(mint(), opts);
  assert.equal(c.ref, "refs/heads/workshop-alice");
});

test("forged, foreign or out-of-scope tokens are refused", async () => {
  const bad = [
    mint({}, { key: other.privateKey }), // not GitHub's key
    mint({}, { header: { kid: "nope" } }),
    mint({}, { header: { alg: "none" } }),
    mint({ aud: "sts.amazonaws.com" }), // the AWS token cannot be replayed here
    mint({ iss: "https://evil.example" }),
    mint({ exp: now - 120 }),
    mint({ nbf: now + 600 }),
    mint({ event_name: "pull_request" }),
    mint({ ref_type: "tag", ref: "refs/tags/v1" }),
    "a.b",
  ];
  for (const t of bad) await assert.rejects(verifyGithubOidc(t, opts), OidcError);
  // Payload swapped under a valid signature.
  const [h, , s] = mint().split(".");
  const tampered = `${h}.${b64({ ref: "refs/heads/workshop-main" })}.${s}`;
  await assert.rejects(verifyGithubOidc(tampered, opts), OidcError);
});
