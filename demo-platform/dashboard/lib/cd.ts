// Continuous delivery for ephemeral (workshop-*/demo-*) branches.
//
// A branch's workflow is code the branch author controls, so nothing it says
// about itself is trusted: the branch, repository and commit come from a
// GitHub-signed OIDC token, the tenant id is derived from that branch here,
// and the image tags a deploy may use are the immutable ones CI pushed for
// that exact commit. Self-contained (node: built-ins only) so it can be unit
// tested with `node --test` without the Next.js toolchain.

import { createPublicKey, verify as verifySignature, type JsonWebKey } from "node:crypto";

export const GITHUB_OIDC_ISSUER = "https://token.actions.githubusercontent.com";

// Mirrors ALL_SERVICES in scripts/lib/tenant-common.sh.
export const CD_SERVICES: ReadonlySet<string> = new Set([
  "api-gateway",
  "auth-service",
  "file-service",
  "document-service",
  "collab-service",
  "notification-service",
  "search-service",
  "analytics-service",
  "admin-service",
  "audit-service",
  "report-service",
  "web-app",
  "admin-dashboard",
]);

const BRANCH_PREFIXES = ["workshop-", "demo-"] as const;
const TENANT_ID = /^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$/;

export type Derived<T> = { ok: true; value: T } | { ok: false; error: string };

/**
 * The tenant a CD branch owns, or why it owns none.
 *
 * Stricter than sanitizeId() on purpose: the id must be exactly what the
 * branch spells (no lowercasing, no character folding, no truncation), so two
 * different branches can never collapse onto one tenant by sanitization, and
 * it may never be a perpetual tenant -- `workshop-main` does not get t-main.
 */
export function cdTenantIdForBranch(
  branch: string,
  prefix: string,
  perpetual: ReadonlySet<string>,
): Derived<string> {
  const kind = BRANCH_PREFIXES.find((p) => branch.startsWith(p));
  if (!kind) return { ok: false, error: `branch '${branch}' is not a workshop-* or demo-* branch` };
  const id = `${prefix ? `${prefix}-` : ""}${branch.slice(kind.length)}`;
  if (!TENANT_ID.test(id) || id.includes("--")) {
    return {
      ok: false,
      error: `branch '${branch}' does not map to a tenant id unambiguously; use lowercase letters, digits and single hyphens (at most 40 characters)`,
    };
  }
  if (perpetual.has(id)) {
    return { ok: false, error: `tenant '${id}' is perpetual and cannot be deployed from branch '${branch}'` };
  }
  return { ok: true, value: id };
}

/** Same as branch_tag_slug in scripts/lib/tenant-common.sh. */
export function branchTagSlug(branch: string): string {
  return branch.toLowerCase().replace(/[^a-z0-9._-]/g, "-");
}

/**
 * Whether `tag` is the immutable build tag CI pushes for this branch at this
 * commit: `[<prefix>-]<slug>-<sha7>`. Anything else -- `main`, `tenant-*`,
 * another branch's build -- is refused, so a branch only deploys its own code.
 */
export function isBuildTagFor(tag: string, branch: string, sha: string, prefix: string): boolean {
  if (!/^[0-9a-f]{40}$/.test(sha)) return false;
  return tag === `${prefix ? `${prefix}-` : ""}${branchTagSlug(branch)}-${sha.slice(0, 7)}`;
}

/** `owner/repo=prefix,owner/repo=` -> map of lowercased repository to TENANT_PREFIX. */
export function parseTrustedRepos(raw: string): Map<string, string> {
  const out = new Map<string, string>();
  for (const entry of raw.split(",")) {
    const trimmed = entry.trim();
    if (!trimmed) continue;
    const eq = trimmed.indexOf("=");
    const repo = (eq === -1 ? trimmed : trimmed.slice(0, eq)).trim().toLowerCase();
    const prefix = eq === -1 ? "" : trimmed.slice(eq + 1).trim();
    if (repo) out.set(repo, prefix);
  }
  return out;
}

export interface GithubOidcClaims {
  iss: string;
  sub: string;
  aud: string | string[];
  repository: string;
  ref: string;
  ref_type: string;
  sha: string;
  event_name: string;
  run_id?: string;
  exp: number;
  nbf?: number;
  iat?: number;
}

export class OidcError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OidcError";
  }
}

function b64urlJson(part: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(Buffer.from(part, "base64url").toString("utf8"));
  if (!parsed || typeof parsed !== "object") throw new OidcError("malformed token");
  return parsed as Record<string, unknown>;
}

const str = (v: unknown): v is string => typeof v === "string" && v.length > 0;

/**
 * Verify a GitHub Actions OIDC token (RS256) for `audience` and return its
 * claims. Only push and workflow_dispatch runs on a branch are accepted.
 */
export async function verifyGithubOidc(
  token: string,
  opts: {
    audience: string;
    getKey: (kid: string) => Promise<JsonWebKey | undefined>;
    now?: number;
  },
): Promise<GithubOidcClaims> {
  const parts = token.split(".");
  if (parts.length !== 3 || parts.some((p) => !p)) throw new OidcError("malformed token");
  const [h, p, s] = parts as [string, string, string];
  let header: Record<string, unknown>;
  let payload: Record<string, unknown>;
  try {
    header = b64urlJson(h);
    payload = b64urlJson(p);
  } catch {
    throw new OidcError("malformed token");
  }
  if (header.alg !== "RS256" || !str(header.kid)) throw new OidcError("unsupported token algorithm");

  const jwk = await opts.getKey(header.kid);
  if (!jwk) throw new OidcError("unknown signing key");
  const ok = verifySignature(
    "RSA-SHA256",
    Buffer.from(`${h}.${p}`),
    createPublicKey({ key: jwk, format: "jwk" }),
    Buffer.from(s, "base64url"),
  );
  if (!ok) throw new OidcError("bad signature");

  const now = opts.now ?? Math.floor(Date.now() / 1000);
  const skew = 60;
  if (payload.iss !== GITHUB_OIDC_ISSUER) throw new OidcError("wrong issuer");
  const aud = payload.aud;
  const audOk = Array.isArray(aud) ? aud.includes(opts.audience) : aud === opts.audience;
  if (!opts.audience || !audOk) throw new OidcError("wrong audience");
  if (typeof payload.exp !== "number" || payload.exp + skew < now) throw new OidcError("token expired");
  if (typeof payload.nbf === "number" && payload.nbf - skew > now) throw new OidcError("token not yet valid");
  if (!str(payload.repository) || !str(payload.ref) || !str(payload.sha) || !str(payload.sub)) {
    throw new OidcError("token is missing repository/ref/sha");
  }
  if (payload.ref_type !== "branch" || !payload.ref.startsWith("refs/heads/")) {
    throw new OidcError("token is not for a branch");
  }
  if (payload.event_name !== "push" && payload.event_name !== "workflow_dispatch") {
    throw new OidcError(`event '${String(payload.event_name)}' may not deploy`);
  }
  return payload as unknown as GithubOidcClaims;
}

// GitHub's signing keys, cached; refetched (at most once a minute) when a
// token names a key we have not seen, which is how GitHub rotates.
let jwks: { keys: Map<string, JsonWebKey>; fetchedAt: number } | null = null;

export async function githubSigningKey(kid: string): Promise<JsonWebKey | undefined> {
  const now = Date.now();
  const stale = !jwks || now - jwks.fetchedAt > 60 * 60 * 1000;
  const miss = !jwks?.keys.has(kid) && (!jwks || now - jwks.fetchedAt > 60 * 1000);
  if (stale || miss) {
    const res = await fetch(`${GITHUB_OIDC_ISSUER}/.well-known/jwks`, { cache: "no-store" });
    if (!res.ok) throw new Error(`GitHub JWKS fetch failed: ${res.status}`);
    const body = (await res.json()) as { keys?: (JsonWebKey & { kid?: string })[] };
    const keys = new Map<string, JsonWebKey>();
    for (const k of body.keys ?? []) if (k.kid && k.kty === "RSA") keys.set(k.kid, k);
    jwks = { keys, fetchedAt: now };
  }
  return jwks?.keys.get(kid);
}
