import { afterEach, expect, it, vi } from "vitest";
import type { LookupFunction } from "node:net";
import dns from "node:dns/promises";
import { dispatchWebhook } from "@/lib/dispatch";
import { TicketService } from "@/lib/service";
import { freshStore, seedProject, seedTicket } from "./helpers";

const captured = vi.hoisted(() => ({ lookup: undefined as LookupFunction | undefined, fetch: vi.fn() }));
vi.mock("undici", () => ({
  Agent: class { constructor(options: { connect: { lookup: LookupFunction } }) { captured.lookup = options.connect.lookup; } async close() {} },
  fetch: captured.fetch,
}));
const mode = process.env.LOCAL_MODE;
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); process.env.LOCAL_MODE = mode; });

it("pins the validated address instead of performing a second DNS lookup", async () => {
  process.env.LOCAL_MODE = "true";
  const svc = new TicketService(freshStore());
  const project = await seedProject(svc);
  const ticket = await seedTicket(svc);
  process.env.LOCAL_MODE = "false";
  const lookup = vi.spyOn(dns, "lookup").mockResolvedValueOnce([{ address: "93.184.216.34", family: 4 }] as never)
    .mockResolvedValue([{ address: "127.0.0.1", family: 4 }] as never);
  const response = new Response(null, { status: 200 });
  captured.fetch.mockResolvedValue(response);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
  expect((await dispatchWebhook(project, ticket, { backoffMs: 0 })).ok).toBe(true);
  expect(captured.lookup).toBeDefined();
  let connectedAddress: unknown;
  captured.lookup!("hook.test", {}, (_error, address) => { connectedAddress = address; });
  expect(connectedAddress).toBe("93.184.216.34");
  expect(lookup).toHaveBeenCalledTimes(1);
});
