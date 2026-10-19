import { NextRequest } from "next/server";
import { withSession, json, error } from "@/lib/api";
import { appendAudit, getTenant, setPinned } from "@/lib/control";
import type { PinRequest } from "@/lib/types";
import { NEVER_TTL_SECONDS, ttlToSeconds } from "@/lib/util";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// What a tenant gets back when it is unpinned: the same lifetime CD gives a
// new branch tenant.
const UNPIN_TTL = "72h";

// Pinning is open to any tenant, unlike `persist`: a pinned tenant still idles
// to zero, so keeping it costs a namespace and a database rather than compute.
export const POST = withSession(async (req: NextRequest, { actor, params }) => {
  const id = params?.id;
  if (!id) return error(400, "missing id");

  const tenant = await getTenant(id);
  if (!tenant) return error(404, "not found");

  const body = (await req.json().catch(() => ({}))) as PinRequest;
  if (typeof body.pinned !== "boolean") return error(400, "missing pinned (boolean)");
  if (tenant.persistent) {
    return error(409, `tenant '${id}' is persistent and already never expires`);
  }

  let ttlSeconds: number;
  if (body.pinned) {
    ttlSeconds = NEVER_TTL_SECONDS;
  } else {
    const ttl = typeof body.ttl === "string" && body.ttl.trim() ? body.ttl.trim() : UNPIN_TTL;
    const seconds = ttlToSeconds(ttl);
    if (seconds === null || seconds >= NEVER_TTL_SECONDS) return error(400, "invalid ttl");
    ttlSeconds = seconds;
  }

  const expiresAt = await setPinned(id, body.pinned, ttlSeconds);

  await appendAudit({
    tenantId: id,
    action: "pin",
    actor,
    detail: body.pinned
      ? "pinned (never reaped, still idle-suspended)"
      : `unpinned (expires_at=${expiresAt})`,
  });

  return json({ ok: true, pinned: body.pinned, expiresAt });
});
