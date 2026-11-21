export type ClassificationLabel = "Restricted" | "Confidential" | "Internal";

export interface Classification {
  label: ClassificationLabel;
  guidance: string;
  chipClassName: string;
}

const RESTRICTED_TERMS = [
  "kyc",
  "beneficial ownership",
  "credit memo",
  "suitability",
  "application packet",
  "sar",
];

const CONFIDENTIAL_TERMS = [
  "statement",
  "payment history",
  "credit review",
  "investment profile",
  "enrollment",
];

export const CLASSIFICATIONS: Record<ClassificationLabel, Classification> = {
  Restricted: {
    label: "Restricted",
    guidance: "Do not share outside the deal team. Downloads are logged.",
    chipClassName: "bg-red-50 text-red-700 border-red-200",
  },
  Confidential: {
    label: "Confidential",
    guidance: "Share only with named colleagues who need it.",
    chipClassName: "bg-amber-50 text-amber-700 border-amber-200",
  },
  Internal: {
    label: "Internal",
    guidance: "For Bank of America employees only.",
    chipClassName: "bg-blue-50 text-blue-700 border-blue-200",
  },
};

function containsAny(haystack: string, terms: string[]): boolean {
  return terms.some((term) => haystack.includes(term));
}

export function classifyFileName(fileName: string): Classification {
  const name = fileName.toLowerCase();
  if (containsAny(name, RESTRICTED_TERMS)) return CLASSIFICATIONS.Restricted;
  if (containsAny(name, CONFIDENTIAL_TERMS)) return CLASSIFICATIONS.Confidential;
  return CLASSIFICATIONS.Internal;
}
