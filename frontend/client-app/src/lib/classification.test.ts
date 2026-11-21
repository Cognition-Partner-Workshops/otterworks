import { describe, it, expect } from "vitest";
import { classifyFileName } from "./classification";

describe("classifyFileName", () => {
  it("labels KYC files Restricted", () => {
    expect(classifyFileName("Harborview Logistics LLC KYC Checklist.docx").label).toBe("Restricted");
  });

  it("labels statements Confidential", () => {
    expect(classifyFileName("Jan 2026 Wealth Account Statement.pdf").label).toBe("Confidential");
  });

  it("defaults to Internal", () => {
    expect(classifyFileName("Checking Rate Sheet 2026.csv").label).toBe("Internal");
  });

  it("picks the most sensitive label when several match", () => {
    expect(classifyFileName("LN-2025-101241 Credit Memo Statement.docx").label).toBe("Restricted");
  });

  it("matches case-insensitively", () => {
    expect(classifyFileName("beneficial ownership form.pdf").label).toBe("Restricted");
    expect(classifyFileName("PAYMENT HISTORY.xlsx").label).toBe("Confidential");
  });

  it("carries the handling guidance for each label", () => {
    expect(classifyFileName("SAR draft.docx").guidance).toMatch(/deal team/);
    expect(classifyFileName("Enrollment.pdf").guidance).toMatch(/named colleagues/);
    expect(classifyFileName("notes.txt").guidance).toMatch(/employees only/);
  });
});
