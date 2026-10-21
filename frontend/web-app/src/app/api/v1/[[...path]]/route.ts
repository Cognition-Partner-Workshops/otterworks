import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_GATEWAY_URL = process.env.API_GATEWAY_URL || "http://localhost:8080";

// Requests that never carry a body.
const BODILESS_METHODS = new Set(["GET", "HEAD"]);

// Upstream connect/response timeout. Without this, an unreachable or slow
// gateway would leave the portal hanging before eventually erroring.
const UPSTREAM_TIMEOUT_MS = 30_000;

async function proxyRequest(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const targetUrl = new URL(pathname + search, API_GATEWAY_URL);

  const headers = new Headers(request.headers);
  headers.delete("host");

  const hasBody = !BODILESS_METHODS.has(request.method);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);

  try {
    // Stream the request body straight through instead of buffering it with
    // request.text(), which hangs on POST bodies under `output: standalone`.
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      // `duplex` is required by the fetch spec when sending a streamed body.
      ...(hasBody ? { duplex: "half" } : {}),
      redirect: "manual",
      signal: controller.signal,
    } as RequestInit);

    const responseHeaders = new Headers(response.headers);
    responseHeaders.delete("transfer-encoding");
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");

    return new NextResponse(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    const timedOut = error instanceof Error && error.name === "AbortError";
    return NextResponse.json(
      {
        error: timedOut
          ? "API gateway timed out"
          : "API gateway unreachable",
      },
      { status: timedOut ? 504 : 502 }
    );
  } finally {
    clearTimeout(timeout);
  }
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
export const OPTIONS = proxyRequest;
