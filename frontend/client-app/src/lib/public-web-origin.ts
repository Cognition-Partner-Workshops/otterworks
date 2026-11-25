export function getPublicWebOrigin(): string | null {
  const configuredOrigin = import.meta.env.VITE_PUBLIC_WEB_ORIGIN;
  if (!configuredOrigin) return null;

  try {
    const origin = new URL(configuredOrigin);
    if (
      (origin.protocol !== "https:" && origin.protocol !== "http:") ||
      origin.username || origin.password || origin.pathname !== "/" ||
      origin.search || origin.hash
    ) {
      return null;
    }
    return origin.origin;
  } catch {
    return null;
  }
}
