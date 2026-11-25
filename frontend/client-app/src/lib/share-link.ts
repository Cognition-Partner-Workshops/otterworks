import { Clipboard } from "@capacitor/clipboard";
import { Capacitor } from "@capacitor/core";
import { getPublicWebOrigin } from "./public-web-origin";

export function getShareLink(resource: "files" | "documents", id: string): string | null {
  const path = `/${resource}/${encodeURIComponent(id)}`;
  if (!Capacitor.isNativePlatform()) return `${window.location.origin}${path}`;

  const origin = getPublicWebOrigin();
  return origin ? `${origin}${path}` : null;
}

export async function copyShareLink(url: string): Promise<void> {
  if (Capacitor.isNativePlatform()) {
    await Clipboard.write({ string: url });
  } else {
    await navigator.clipboard.writeText(url);
  }
}
