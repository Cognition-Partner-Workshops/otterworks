import { NextRequest } from "next/server";
import { error, json, translateError } from "@/lib/api";
import { appendAudit, checkout, extend, getTenant, setServiceImages } from "@/lib/control";
import { activeRunnerJob, createRunnerJob } from "@/lib/jobs";
import { env } from "@/lib/env";
import { hostSuffixOf, secondsToTtl, ttlToSeconds } from "@/lib/util";
import {
  CD_SERVICES,
  OidcError,
  cdTenantIdForBranch,
  githubSigningKey,
  isBuildTagFor,
  parseTrustedRepos,
  verifyGithubOidc,
} from "@/lib/cd";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const CD_TTL = "72h";

/**
 * Ship a workshop-* or demo-* push to the tenant that branch owns.
 *
 * The caller is the branch's own workflow, i.e. code the branch author wrote,
 * so it holds no dashboard passcode and nothing it claims about itself is
 * believed. Who it is comes from a GitHub-signed OIDC token: the repository
 * picks the tenant prefix, the branch picks the tenant (strictly -- see
 * cdTenantIdForBranch), and the only images it may deploy are the immutable
 * build tags CI pushed for that commit. The ownership check happens here,
 * before anything about the tenant changes, and no moving image tag is ever
 * touched: the tenant runs its builds by tag, everything else from `main`.
 */
export async function POST(req: NextRequest) {
  try {
    if (!env.cdOidcAudience) return error(404, "not found");

    const m = /^Bearer\s+(\S+)$/i.exec(req.headers.get("authorization") ?? "");
    if (!m?.[1]) return error(401, "missing bearer token");

    let claims;
    try {
      claims = await verifyGithubOidc(m[1], { audience: env.cdOidcAudience, getKey: githubSigningKey });
    } catch (err) {
      if (err instanceof OidcError) return error(401, `invalid token: ${err.message}`);
      throw err;
    }

    const prefix = parseTrustedRepos(env.cdTrustedRepos).get(claims.repository.toLowerCase());
    if (prefix === undefined) return error(403, `repository '${claims.repository}' may not deploy`);

    const branch = claims.ref.slice("refs/heads/".length);
    const derived = cdTenantIdForBranch(branch, prefix, env.perpetualTenantIds);
    if (!derived.ok) return error(403, derived.error);
    const id = derived.value;

    const body = (await req.json().catch(() => ({}))) as { image_tag?: unknown; services?: unknown };
    const services = Array.isArray(body.services) ? body.services : [];
    if (!services.every((s): s is string => typeof s === "string" && CD_SERVICES.has(s))) {
      return error(400, "services must be a list of known service names");
    }
    const imageTag = typeof body.image_tag === "string" ? body.image_tag : "";
    if (services.length > 0 && !isBuildTagFor(imageTag, branch, claims.sha, prefix)) {
      return error(403, `image_tag must be this commit's build tag`);
    }
    const built = Object.fromEntries(services.map((s) => [s, imageTag]));
    const actor = `ci:${claims.repository}@${branch}`;

    const tenant = await getTenant(id);

    if (!tenant || tenant.status === "free") {
      const inFlight = await activeRunnerJob(id, "deploy");
      if (inFlight) return error(409, `deploy already running for '${id}' (${inFlight})`);
      const created = await checkout({
        id,
        owner: "ci",
        branch,
        tier: "A",
        ttlSeconds: ttlToSeconds(CD_TTL) ?? 72 * 3600,
        hostSuffix: env.hostSuffix,
        serviceImages: built,
      });
      const job = await createRunnerJob({
        action: "deploy",
        tenantId: id,
        branch,
        tier: created.tier,
        ttl: CD_TTL,
        hostSuffix: env.hostSuffix,
        serviceImageTags: built,
      });
      await appendAudit({ tenantId: id, action: "checkout", actor, detail: `sha=${claims.sha} job=${job}` });
      return json({ ok: true, created: true, tenant: id, job }, 201);
    }

    // A tenant belongs to the branch it was checked out from; demo-x may not
    // redeploy workshop-x. Perpetual and pinned environments are operator-owned.
    if (tenant.branch !== branch) {
      return error(409, `tenant '${id}' is deployed from '${tenant.branch ?? "(none)"}', not '${branch}'`);
    }
    if (tenant.persistent) return error(403, `tenant '${id}' is perpetual`);
    if (tenant.status === "draining") return error(409, `tenant '${id}' is draining`);

    const inFlight = await activeRunnerJob(id, "deploy");
    if (inFlight) return error(409, `deploy already running for '${id}' (${inFlight})`);

    const images = { ...(tenant.serviceImages ?? {}), ...built };
    await setServiceImages(id, branch, images);

    // A push counts as use: CD_TTL from now, never shorter than what is left.
    let ttl = "never";
    if (!tenant.pinned) {
      const now = Math.floor(Date.now() / 1000);
      const target = now + (ttlToSeconds(CD_TTL) ?? 72 * 3600);
      const expiresAt = target > tenant.expiresAt ? await extend(id, target - now) : tenant.expiresAt;
      ttl = secondsToTtl(Math.max(300, expiresAt - now));
    }

    let job: string;
    try {
      job = await createRunnerJob({
        action: "deploy",
        tenantId: id,
        branch,
        tier: tenant.tier,
        ttl,
        hostSuffix: hostSuffixOf(tenant.url) ?? env.hostSuffix,
        redeploy: true,
        serviceImageTags: images,
      });
    } catch (err) {
      await appendAudit({
        tenantId: id,
        action: "deploy_fail",
        actor,
        detail: err instanceof Error ? err.message : "job create failed",
      });
      throw err;
    }
    await appendAudit({ tenantId: id, action: "redeploy", actor, detail: `sha=${claims.sha} job=${job}` });
    return json({ ok: true, created: false, tenant: id, job });
  } catch (err) {
    return translateError(err);
  }
}
