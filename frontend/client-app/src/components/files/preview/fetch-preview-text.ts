import { TEXT_PREVIEW_BYTES } from "@/lib/preview-kind";

export interface PreviewText {
  text: string;
  truncated: boolean;
}

export async function fetchPreviewText(url: string, signal: AbortSignal): Promise<PreviewText> {
  const response = await fetch(url, {
    headers: { Range: `bytes=0-${TEXT_PREVIEW_BYTES - 1}` },
    signal,
  });
  if (response.status !== 200 && response.status !== 206) {
    throw new Error(`Text preview failed with status ${response.status}`);
  }

  const { bytes, overflow } = await readBoundedBody(response, TEXT_PREVIEW_BYTES);
  const range = response.headers.get("Content-Range")?.match(/\/(\d+)$/);
  const contentLength = Number(response.headers.get("Content-Length"));
  const truncated = overflow ||
    contentLength > TEXT_PREVIEW_BYTES ||
    (range ? Number(range[1]) > TEXT_PREVIEW_BYTES : false);
  return {
    text: new TextDecoder("utf-8").decode(bytes),
    truncated,
  };
}

async function readBoundedBody(
  response: Response,
  limit: number,
): Promise<{ bytes: Uint8Array; overflow: boolean }> {
  if (!response.body) {
    const buffer = new Uint8Array(await response.arrayBuffer());
    return { bytes: buffer.subarray(0, limit), overflow: buffer.byteLength > limit };
  }

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  let overflow = false;
  while (length < limit) {
    const { done, value } = await reader.read();
    if (done) break;
    const remaining = limit - length;
    chunks.push(value.subarray(0, remaining));
    length += Math.min(value.byteLength, remaining);
    if (value.byteLength > remaining) {
      overflow = true;
      await reader.cancel();
      break;
    }
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return { bytes, overflow };
}
