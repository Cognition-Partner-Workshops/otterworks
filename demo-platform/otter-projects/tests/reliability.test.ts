import net from "node:net";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { DYNAMO_REQUEST_TIMEOUT_MS, DynamoStore } from "@/lib/store/dynamo";
import { LocalStore } from "@/lib/store/local";
import { setStore } from "@/lib/store";
import { TicketService } from "@/lib/service";
import type { WebhookDelivery } from "@/lib/types";
import { fetchQueue, freshStore, seedProject, seedTicket } from "./helpers";

const ENV = { ...process.env };
beforeEach(() => {
  process.env.LOCAL_MODE = "true";
  process.env.DEVIN_API_KEY = "cog_test";
  process.env.DEVIN_ORG_ID = "org-123";
  process.env.PROJECTS_PUBLIC_URL = "https://projects.example.test";
});
afterEach(() => {
  process.env = { ...ENV };
});

describe("DynamoStore transport", () => {
  it("fails fast instead of hanging when DynamoDB accepts but never answers", async () => {
    const sockets: net.Socket[] = [];
    const server = net.createServer((s) => sockets.push(s));
    await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
    const port = (server.address() as net.AddressInfo).port;
    process.env.AWS_ACCESS_KEY_ID = "test";
    process.env.AWS_SECRET_ACCESS_KEY = "test";
    process.env.AWS_ENDPOINT_URL_DYNAMODB = `http://127.0.0.1:${port}`;
    process.env.AWS_MAX_ATTEMPTS = "1";
    try {
      const store = new DynamoStore("t", "us-east-1");
      const started = Date.now();
      await expect(store.getProject("OTTER")).rejects.toThrow();
      expect(sockets.length).toBeGreaterThan(0);
      expect(Date.now() - started).toBeLessThan(DYNAMO_REQUEST_TIMEOUT_MS + 2000);
    } finally {
      sockets.forEach((s) => s.destroy());
      await new Promise((r) => server.close(r));
    }
  }, 15_000);
});

describe("Devin message mirroring", () => {
  it("concurrent deliveries of the same Devin message add one comment", async () => {
    const store = freshStore();
    const svc = new TicketService(store);
    await seedProject(svc);
    const t = await seedTicket(svc);
    const ev = { ticket: t.key, session_id: "devin-1", message: "dup", message_id: "ev-9", message_at: 5000 };
    await Promise.all([svc.applyDevinEvent(ev), svc.applyDevinEvent(ev)]);
    expect((await store.listComments(t.key)).filter((c) => c.body === "dup")).toHaveLength(1);
  });
});

class FlakyDeliveryStore extends LocalStore {
  async addDelivery(_d: WebhookDelivery): Promise<void> {
    throw new Error("delivery table unavailable");
  }
}

describe("dispatch bookkeeping", () => {
  it("keeps the created Devin session when the delivery audit write fails", async () => {
    const store = new FlakyDeliveryStore("");
    setStore(store);
    const q = fetchQueue([{ status: 200, body: { session_id: "devin-xyz", url: "https://app.devin.ai/sessions/xyz", status: "new", pull_requests: [], updated_at: 1 } }]);
    const svc = new TicketService(store, { fetch: q.fn, backoffMs: 0 });
    await seedProject(svc, { dispatcher: "devin-api" });
    const t = await seedTicket(svc);
    const res = await svc.assignToDevin(t.key, "tester").catch((e: unknown) => ({ ok: false, error: String(e) }));
    expect(res.ok).toBe(true);
    expect((await store.getTicket(t.key))!.devin.sessionId).toBe("devin-xyz");
    expect(q.calls).toHaveLength(1);
  });
});
