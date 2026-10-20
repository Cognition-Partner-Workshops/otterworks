import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { CORPUS, corpusIds, hasTool, mapToCanonical, validate } from "./contract-tools";

// Pins the hub contract this client targets: the vendored schema and map,
// run over the hub's own FNOL corpus, must reproduce the hub's goldens.
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
