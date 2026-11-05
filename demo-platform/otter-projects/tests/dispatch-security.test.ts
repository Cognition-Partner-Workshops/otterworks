import { afterEach, expect, it, vi } from "vitest";
import { createServer } from "node:http";
import { dispatchWebhook } from "@/lib/dispatch";
import { TicketService } from "@/lib/service";
import { freshStore, seedProject, seedTicket } from "./helpers";

const previousMode = process.env.LOCAL_MODE;
afterEach(() => { vi.unstubAllGlobals(); process.env.LOCAL_MODE = previousMode; });

it.each(["198.18.0.1", "192.0.0.8", "240.1.2.3", "[::ffff:c0a8:1]", "[febf::1]"])("blocks reserved or mapped private destination %s", async (host) => {
  process.env.LOCAL_MODE = "true";
  const svc = new TicketService(freshStore());
  const project = await seedProject(svc);
  const ticket = await seedTicket(svc);
  process.env.LOCAL_MODE = "false";
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 200 })));
  const result = await dispatchWebhook({ ...project, webhookUrl: `https://${host}/hook` }, ticket, { backoffMs: 0 });
  expect(result.ok).toBe(false);
  expect(result.delivery.error).toContain("private");
});

it("does not follow a webhook redirect into a private destination", async () => {
  process.env.LOCAL_MODE = "true";
  let privateRequests = 0;
  const server = createServer((req, res) => {
    if (req.url === "/hook") { res.writeHead(302, { Location: "/private" }).end(); }
    else { privateRequests++; res.writeHead(200).end(); }
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const address = server.address();
    if (!address || typeof address === "string") throw new Error("No server address");
    const svc = new TicketService(freshStore());
    const project = await seedProject(svc);
    const result = await dispatchWebhook({ ...project, webhookUrl: `http://127.0.0.1:${address.port}/hook` }, await seedTicket(svc), { backoffMs: 0 });
    expect(result.ok).toBe(false);
    expect(privateRequests).toBe(0);
  } finally { await new Promise<void>((resolve) => server.close(() => resolve())); }
});
