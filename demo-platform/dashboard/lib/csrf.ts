// Cross-site request forgery guard for state-changing /api requests.
//
// The session cookie is SameSite=Strict, but every tenant frontend
// (t-<id>.demo.otterworks.app, t-main.otterworks.app) shares the registrable
// domain with ops.otterworks.app, so a browser treats them as the same *site*
// and still attaches the cookie to a request a tenant page forges. Two
// independent checks close that path:
//
//  1. The request must come from the dashboard's own origin. Browsers always
//     send `Sec-Fetch-Site` and/or `Origin` on a non-GET request, so one that
//     carries neither (and no `Referer`) is a non-browser client such as
//     `demo-platform/scripts/tenant.sh`, which the cookie model cannot be
//     forged against. Anything a browser labels cross-site/cross-origin is
//     refused.
//  2. The body must be declared `application/json`. A cross-origin browser
//     request with that content type needs a CORS preflight the dashboard
//     never approves, so the `text/plain` form/no-cors trick cannot reach a
//     handler's `req.json()`.
//
// This file must stay Edge-safe (no node: imports): middleware.ts runs it on
// the Edge runtime and lib/api.ts runs it again in the Node handlers.

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export interface CsrfRejection {
  status: 403 | 415;
  message: string;
}

export function isStateChanging(method: string): boolean {
  return !SAFE_METHODS.has(method.toUpperCase());
}

function hostOf(value: string): string | null {
  try {
    return new URL(value).host.toLowerCase();
  } catch {
    return null;
  }
}

function mediaType(contentType: string | null): string {
  return (contentType ?? "").split(";")[0]?.trim().toLowerCase() ?? "";
}

/**
 * Returns why a state-changing request must be refused, or null when it may
 * proceed. Safe methods always pass.
 */
export function csrfRejection(method: string, headers: Headers): CsrfRejection | null {
  if (!isStateChanging(method)) return null;

  const fetchSite = headers.get("sec-fetch-site");
  if (fetchSite !== null && fetchSite !== "same-origin") {
    return { status: 403, message: "cross-site request refused" };
  }

  const ownHost = (headers.get("x-forwarded-host") ?? headers.get("host") ?? "")
    .split(",")[0]
    ?.trim()
    .toLowerCase();
  const source = headers.get("origin") ?? headers.get("referer");
  if (source !== null) {
    const sourceHost = hostOf(source);
    if (!ownHost || sourceHost === null || sourceHost !== ownHost) {
      return { status: 403, message: "cross-origin request refused" };
    }
  }

  if (mediaType(headers.get("content-type")) !== "application/json") {
    return { status: 415, message: "content-type must be application/json" };
  }

  return null;
}
