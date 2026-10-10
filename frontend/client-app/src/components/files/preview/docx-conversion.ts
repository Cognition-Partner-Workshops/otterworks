import mammoth from "mammoth";

export async function convertDocxToHtml(buffer: ArrayBuffer): Promise<string> {
  const result = await mammoth.convertToHtml({ arrayBuffer: buffer });
  return result.value;
}
