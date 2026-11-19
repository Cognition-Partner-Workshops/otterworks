import { Clipboard } from "@capacitor/clipboard";
import { Capacitor } from "@capacitor/core";

export function getShareLink(resource: "files" | "documents", id: string): string | null {
  const path = `/${resource}/${encodeURIComponent(id)}`;
  if (!Capacitor.isNativePlatform()) return `${window.location.origin}${path}`;

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
    return `${origin.origin}${path}`;
  } catch {
    return null;
  }
}

export async function copyShareLink(url: string): Promise<void> {
  if (Capacitor.isNativePlatform()) {
    await Clipboard.write({ string: url });
  } else {
    await navigator.clipboard.writeText(url);
  }
}
