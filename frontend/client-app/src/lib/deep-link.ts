const resourcePath = /^\/(files|documents)\/[a-zA-Z0-9_-]+$/;

export function isResourcePath(path: unknown): path is string {
  return typeof path === "string" && resourcePath.test(path);
}

export function getDeepLinkPath(value: string, publicOrigin: string | null): string | null {
  const rawPath = /^[a-z]+:\/\/[^/\\?#]+(\/[^\\?#]*)/i.exec(value)?.[1];
  if (!rawPath) return null;

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return null;
  }
  if (url.username || url.password || url.pathname !== rawPath) return null;

  const path = url.protocol === "otterworks:"
    ? `/${url.host.toLowerCase()}${url.pathname}`
    : url.protocol === "https:" && url.origin === publicOrigin
      ? url.pathname
      : null;

  return isResourcePath(path) ? path : null;
}
