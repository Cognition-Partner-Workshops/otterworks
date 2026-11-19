export function rewriteStorageUrl(url: string, publicUrl = import.meta.env.VITE_STORAGE_PUBLIC_URL): string {
  try {
    const source = new URL(url);
    if (source.hostname !== "localstack") return url;
    if (!publicUrl) return url.replace("://localstack:", "://localhost:");
    const target = new URL(publicUrl);
    if (!["http:", "https:"].includes(target.protocol)) return url;
    return url.replace(/^[a-z][a-z\d+.-]*:\/\/[^/?#]*/i, target.origin);
  } catch {
    return url;
  }
}
