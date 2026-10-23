import { NextRequest } from "next/server";
import { withSession, json, error } from "@/lib/api";
import { appendAudit, getTenant } from "@/lib/control";
import { activeRunnerJob, createRunnerJob } from "@/lib/jobs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Scales an idle-suspended tenant back up without touching its record. Check-out
// refuses a tenant that is still reserved, which is exactly the state an idle
// pinned (or checked-out) tenant sleeps in.
export const POST = withSession(async (_req: NextRequest, { actor, params }) => {
  const id = params?.id;
  if (!id) return error(400, "missing id");

  const tenant = await getTenant(id);
  if (!tenant) return error(404, "not found");
  if (tenant.status !== "active") {
    return error(409, `tenant '${id}' is ${tenant.status}; only an active tenant can be woken`);
  }

  const running = await activeRunnerJob(id, "wake");
  if (running) return json({ ok: true, job: running });

  await appendAudit({ tenantId: id, action: "wake", actor, detail: "scale deployments to 1" });
  const jobName = await createRunnerJob({ action: "wake", tenantId: id });
  return json({ ok: true, job: jobName });
});
