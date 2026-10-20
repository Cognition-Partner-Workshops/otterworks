import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  LOSS_CAUSE_CODES,
  MOBILE_PRODUCER,
  buildClaimsSvcRq,
  lineOfBusinessFor,
  maskTaxId,
  newEnvelope,
  normaliseAmount,
  type FnolDraft,
  type FnolEnvelope,
} from "./acord";
import { CORPUS, corpusIds, hasTool, mapToCanonical, validate } from "./contract-tools";

const draft: FnolDraft = {
  policyNumber: "pol-auto-48100",
  lineOfBusiness: "AUTO",
  givenName: "Imogen",
  surname: "Castellanos",
  taxId: "100-40-7000",
  lossDate: "2026-09-02",
  causeCode: "GLAS",
  description: "Windscreen cracked by road debris on the interstate",
  estimatedLossAmt: "412",
  injuries: false,
  city: "Bristol",
  stateProvCd: "ri",
  postalCode: "02809",
};
const env: FnolEnvelope = {
  rqUID: "6f1c3a2e-0000-4b1a-9c0d-000000000000",
  transactionRequestDt: "2026-09-02T08:15:00",
  reportedDt: "2026-09-02",
  claimNumber: "CLM-2026-100400",
  producer: { id: "AG-0417", name: "Harbourline Brokers" },
};

describe("maskTaxId (PiiMaskingComponent.Mask parity)", () => {
  it.each([
    ["123-45-6789", "XXX-XX-6789"],
    ["123456789", "XXXXX6789"],
    ["AB-12-3456", "XX-XX-3456"],
    ["6789", "6789"],
    ["12", "12"],
    ["", ""],
    ["XXX-XX-6789", "XXX-XX-6789"],
  ])("%s -> %s", (raw, masked) => {
    expect(maskTaxId(raw)).toBe(masked);
  });
});

describe("buildClaimsSvcRq", () => {
  const xml = buildClaimsSvcRq(draft, env);

  it("never serialises the raw tax id", () => {
    expect(xml).not.toContain("100-40-7000");
    expect(xml).toContain("<TaxId>XXX-XX-7000</TaxId>");
  });

  it("omits TaxId when the adjuster leaves it blank", () => {
    expect(buildClaimsSvcRq({ ...draft, taxId: "  " }, env)).not.toContain("<TaxId>");
  });

  it("normalises policy, state and amount", () => {
    expect(xml).toContain("<PolicyNumber>POL-AUTO-48100</PolicyNumber>");
    expect(xml).toContain("<StateProvCd>RI</StateProvCd>");
    expect(xml).toContain("<EstimatedLossAmt>412.00</EstimatedLossAmt>");
    expect(xml).toContain("<InjuryInd>false</InjuryInd>");
  });

  it("escapes free text", () => {
    const out = buildClaimsSvcRq({ ...draft, description: `Tree <oak> & "branch"` }, env);
    expect(out).toContain("<IncidentDesc>Tree &lt;oak&gt; &amp; &quot;branch&quot;</IncidentDesc>");
  });

  it("offers exactly the hub's eight cause codes and rejects others", () => {
    expect(LOSS_CAUSE_CODES).toEqual(["COLL", "COMP", "GLAS", "THFT", "FIRE", "WATR", "WIND", "LIAB"]);
    expect(() => buildClaimsSvcRq({ ...draft, causeCode: "TOWG" as never }, env)).toThrow(/Unknown cause/);
  });
});

describe("helpers", () => {
  it("derives line of business from the policy prefix", () => {
    expect(lineOfBusinessFor("POL-HOME-48142")).toBe("HOME");
    expect(lineOfBusinessFor("pol-auto-1")).toBe("AUTO");
    expect(lineOfBusinessFor("POL-LIFE-1")).toBeUndefined();
  });

  it("normalises amounts without float rounding", () => {
    expect(normaliseAmount("412")).toBe("412.00");
    expect(normaliseAmount("0.1")).toBe("0.10");
    expect(normaliseAmount("1234567.89")).toBe("1234567.89");
    expect(() => normaliseAmount("1.234")).toThrow();
    expect(() => normaliseAmount("-5")).toThrow();
  });

  it("stamps a mobile envelope", () => {
    const e = newEnvelope(new Date(2026, 9, 20, 6, 5, 9), () => "abcdef12-3456-7890-abcd-ef1234567890");
    expect(e).toEqual({
      rqUID: "abcdef12-3456-7890-abcd-ef1234567890",
      transactionRequestDt: "2026-10-20T06:05:09",
      reportedDt: "2026-10-20",
      claimNumber: "CLM-2026-MABCDEF12",
      producer: MOBILE_PRODUCER,
    });
  });
});

// Re-key every hub corpus notice through the mobile builder, run the hub map
// over it and compare with the hub's golden canonical claim. Fields the
// mobile screen does not capture are the only allowed differences.
const tools = hasTool("xmllint") && hasTool("xsltproc");
const text = (doc: Document, tag: string) => doc.getElementsByTagName(tag)[0]?.textContent ?? "";

function fromCorpus(id: string): { draft: FnolDraft; env: FnolEnvelope } {
  const doc = new DOMParser().parseFromString(readFileSync(join(CORPUS, `${id}.fnol.xml`), "utf8"), "application/xml");
  return {
    env: {
      rqUID: text(doc, "RqUID"),
      transactionRequestDt: text(doc, "TransactionRequestDt"),
      reportedDt: text(doc, "ReportedDt"),
      claimNumber: text(doc, "ClaimNumber"),
      producer: { id: text(doc, "ProducerId"), name: text(doc, "ProducerName") },
    },
    draft: {
      policyNumber: text(doc, "PolicyNumber"),
      lineOfBusiness: text(doc, "LOBCd") as FnolDraft["lineOfBusiness"],
      givenName: text(doc, "GivenName"),
      surname: text(doc, "Surname"),
      taxId: text(doc, "TaxId") || undefined,
      lossDate: text(doc, "LossDt"),
      causeCode: text(doc, "LossCauseCd") as FnolDraft["causeCode"],
      description: text(doc, "IncidentDesc"),
      estimatedLossAmt: text(doc, "EstimatedLossAmt"),
      injuries: text(doc, "InjuryInd") === "true",
      city: text(doc, "City"),
      stateProvCd: text(doc, "StateProvCd"),
      postalCode: text(doc, "PostalCode"),
    },
  };
}

function canonicalFields(xml: string): Record<string, string> {
  const doc = new DOMParser().parseFromString(xml, "application/xml");
  const out: Record<string, string> = {};
  const walk = (el: Element, prefix: string) => {
    const kids = Array.from(el.children);
    if (!kids.length) out[prefix] = el.textContent ?? "";
    kids.forEach((k) => walk(k, prefix ? `${prefix}/${k.localName}` : k.localName));
  };
  walk(doc.documentElement, "");
  return out;
}

export function corpusParity() {
  const dir = mkdtempSync(join(tmpdir(), "fnol-parity-"));
  return corpusIds().map((id) => {
    const { draft: d, env: e } = fromCorpus(id);
    if (!LOSS_CAUSE_CODES.includes(d.causeCode)) return { id, outcome: `not offered: ${d.causeCode}`, deltas: [] as string[] };
    const path = join(dir, `${id}.xml`);
    writeFileSync(path, buildClaimsSvcRq(d, e));
    validate(path);
    const golden = canonicalFields(readFileSync(join(CORPUS, `${id}.canonical.xml`), "utf8"));
    const mobile = canonicalFields(mapToCanonical(path));
    const keys = [...new Set([...Object.keys(golden), ...Object.keys(mobile)])].sort();
    const deltas = keys.filter((k) => golden[k] !== mobile[k]).map((k) => `${k}: ${golden[k] ?? "-"} -> ${mobile[k] ?? "-"}`);
    return { id, outcome: deltas.length ? "differs" : "identical", deltas };
  });
}

describe.skipIf(!tools)("corpus parity through the mobile builder", () => {
  // Not captured on the screen: VIN/driveable, phone, email, police report and
  // prior-fraud flag. The map omits the first four and defaults the flags to false.
  const NOT_CAPTURED = /^(Vehicle\/|Claimant\/(Email|Phone): |Loss\/PoliceReport: true -> false|Claimant\/PriorFraudFlag: true -> false)/;
  const rows = tools ? corpusParity() : [];

  it("re-keys 15 of 16 notices; TOWG is not one of the eight offered causes", () => {
    expect(rows.filter((r) => r.outcome.startsWith("not offered"))).toEqual([
      { id: "CLM-2026-100402", outcome: "not offered: TOWG", deltas: [] },
    ]);
  });

  it.each(rows.filter((r) => !r.outcome.startsWith("not offered")))(
    "$id maps to the golden on every captured field",
    ({ deltas }) => {
      expect(deltas.filter((d) => !NOT_CAPTURED.test(d))).toEqual([]);
    },
  );

  it("counts the defaulted flags the hub would see differently", () => {
    const all = rows.flatMap((r) => r.deltas.map((d) => `${r.id} ${d}`));
    expect(all.filter((d) => d.includes("PoliceReport"))).toHaveLength(5);
    expect(all.filter((d) => d.includes("PriorFraudFlag"))).toEqual([
      "CLM-2026-100410 Claimant/PriorFraudFlag: true -> false",
    ]);
  });
});
