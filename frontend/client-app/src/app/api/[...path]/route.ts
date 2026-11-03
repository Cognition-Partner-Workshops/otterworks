import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const BASE = process.env.ORDER_SERVICE_URL ?? "http://localhost:8080";
const FORWARD_REQUEST = ["content-type", "cookie", "authorization", "accept"];
const FORWARD_RESPONSE = ["content-type", "cache-control"];

async function proxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const target = `${BASE}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  for (const h of FORWARD_REQUEST) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }
  const body = req.method === "GET" || req.method === "HEAD" ? undefined : await req.arrayBuffer();
  let upstream: Response;
  try {
    upstream = await fetch(target, { method: req.method, headers, body, cache: "no-store", redirect: "manual" });
  } catch {
    return Response.json({ error: "UPSTREAM_UNAVAILABLE", message: "The store is having trouble right now. Try again in a moment." }, { status: 502 });
  }
  const out = new Headers();
  for (const h of FORWARD_RESPONSE) {
    const v = upstream.headers.get(h);
    if (v) out.set(h, v);
  }
  for (const c of upstream.headers.getSetCookie()) out.append("set-cookie", c);
  const status = upstream.status;
  const payload = status === 204 || status === 304 ? null : await upstream.arrayBuffer();
  return new Response(payload, { status, headers: out });
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as PUT, proxy as DELETE };
