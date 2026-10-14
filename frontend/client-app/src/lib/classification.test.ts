import { describe, it, expect } from "vitest";
import { classifyFile } from "./classification";

// PRD: Data classification labels in the Document Vault — acceptance criteria.
describe("classifyFile", () => {
  it("labels KYC files Restricted", () => {
    expect(classifyFile("Harborview Logistics LLC KYC Checklist.docx").label).toBe("Restricted");
  });

  it("labels statements Confidential", () => {
    expect(classifyFile("Jan 2026 Wealth Account Statement.pdf").label).toBe("Confidential");
  });

  it("defaults everything else to Internal", () => {
    expect(classifyFile("Checking Rate Sheet 2026.csv").label).toBe("Internal");
  });

  it("picks the most sensitive label when several match", () => {
    expect(classifyFile("LN-2025-101241 Credit Memo Statement.docx").label).toBe("Restricted");
  });

  it("matches keywords case-insensitively", () => {
    expect(classifyFile("beneficial OWNERSHIP form.pdf").label).toBe("Restricted");
    expect(classifyFile("PAYMENT HISTORY q3.xlsx").label).toBe("Confidential");
  });

  it("covers every keyword in the PRD table", () => {
    for (const name of ["Suitability.pdf", "Application Packet.zip", "SAR filing.docx"]) {
      expect(classifyFile(name).label).toBe("Restricted");
    }
    for (const name of ["Credit Review.pdf", "Investment Profile.docx", "Enrollment form.pdf"]) {
      expect(classifyFile(name).label).toBe("Confidential");
    }
  });

  it("matches keywords as whole words, not inside other words", () => {
    expect(classifyFile("SAR Case Index.csv").label).toBe("Restricted");
    expect(classifyFile("Saratoga Account Statement.pdf").label).toBe("Confidential");
    expect(classifyFile("Harborview-KYC-Checklist.docx").label).toBe("Restricted");
  });

  it("treats underscores and other separators as word boundaries", () => {
    expect(classifyFile("KYC_2026.pdf").label).toBe("Restricted");
    expect(classifyFile("Beneficial_Ownership_Form.pdf").label).toBe("Restricted");
    expect(classifyFile("credit-memo_v2.docx").label).toBe("Restricted");
    expect(classifyFile("payment.history.xlsx").label).toBe("Confidential");
  });

  it("returns the handling guidance for each label", () => {
    expect(classifyFile("KYC.pdf").guidance).toBe("Do not share outside the deal team. Downloads are logged.");
    expect(classifyFile("Statement.pdf").guidance).toBe("Share only with named colleagues who need it.");
    expect(classifyFile("Memo.pdf").guidance).toBe("For Bank of America employees only.");
  });
});
