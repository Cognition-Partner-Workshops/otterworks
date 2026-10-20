import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Pins the hub contract this client targets: the vendored schema and map,
// run over the hub's own FNOL corpus, must reproduce the hub's goldens.
export const CONTRACT = join(__dirname, "..", "contract");
export const XSD = join(CONTRACT, "ACORD_ClaimsNotificationAddRq.xsd");
export const MAP = join(CONTRACT, "Fnol_to_CanonicalClaim.xslt");
export const CORPUS = join(CONTRACT, "corpus");

export const hasTool = (bin: string) => {
  try {
    execFileSync(bin, ["--version"], { stdio: "pipe" });
    return true;
  } catch {
    return false;
  }
};

export const validate = (path: string) =>
  execFileSync("xmllint", ["--noout", "--schema", XSD, path], { stdio: "pipe" });

export const mapToCanonical = (path: string) =>
  execFileSync("xsltproc", [MAP, path], { stdio: "pipe" }).toString().trim();

export const corpusIds = () =>
  readdirSync(CORPUS)
    .filter((f) => f.endsWith(".fnol.xml"))
    .map((f) => f.replace(".fnol.xml", ""))
    .sort();

const tools = hasTool("xmllint") && hasTool("xsltproc");

describe.skipIf(!tools)("hub contract pin (Fnol_to_CanonicalClaim)", () => {
  it("vendors the full 16-notice corpus", () => {
    expect(corpusIds()).toHaveLength(16);
  });

  it.each(corpusIds())("%s validates and maps to its golden", (id) => {
    const input = join(CORPUS, `${id}.fnol.xml`);
    expect(() => validate(input)).not.toThrow();
    const golden = readFileSync(join(CORPUS, `${id}.canonical.xml`), "utf8").trim();
    expect(mapToCanonical(input)).toBe(golden);
  });
});
