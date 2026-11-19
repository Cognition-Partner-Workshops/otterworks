import { Capacitor, CapacitorHttp } from "@capacitor/core";
import { Directory, Encoding, Filesystem } from "@capacitor/filesystem";
import { Share } from "@capacitor/share";

export const isNativePlatform = () => Capacitor.isNativePlatform();

export function safeFileName(name: string): string {
  const cleaned = name.replace(/[/\\:\u0000-\u001f]/g, "_").replace(/^\.+/, "").trim();
  return cleaned || "download";
}

export function versionFileName(name: string, versionNumber: number): string {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? `${name.slice(0, dot)} (v${versionNumber})${name.slice(dot)}` : `${name} (v${versionNumber})`;
}

// Saves into the app's Documents folder (visible in the Files app under
// On My iPhone > OtterWorks), then offers the share sheet. Resolves once the
// file is written; dismissing the share sheet keeps the saved copy.
async function saveAndShare(fileName: string, data: string, encoding?: Encoding): Promise<string> {
  const path = safeFileName(fileName);
  const { uri } = await Filesystem.writeFile({ path, data, directory: Directory.Documents, encoding, recursive: true });
  Share.share({ title: path, files: [uri] }).catch(() => undefined);
  return uri;
}

export async function saveUrlToDevice(url: string, fileName: string): Promise<string> {
  const response = await CapacitorHttp.get({ url, responseType: "blob" });
  if (response.status < 200 || response.status >= 300) {
    throw new Error(`Download failed with HTTP ${response.status}`);
  }
  // CapacitorHttp parses application/json bodies even when a blob is requested.
  if (response.data !== null && typeof response.data === "object") {
    return saveAndShare(fileName, JSON.stringify(response.data, null, 2), Encoding.UTF8);
  }
  if (typeof response.data !== "string") throw new Error("Download returned no file data");
  return saveAndShare(fileName, response.data);
}

export function saveTextToDevice(text: string, fileName: string): Promise<string> {
  return saveAndShare(fileName, text, Encoding.UTF8);
}

export function downloadUrlInBrowser(url: string, fileName: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
