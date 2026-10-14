export type ClassificationLabel = "Restricted" | "Confidential" | "Internal";

export interface Classification {
  label: ClassificationLabel;
  guidance: string;
  chipClassName: string;
}

// Ordered most to least sensitive: the first matching rule wins.
const RULES: ReadonlyArray<{ label: ClassificationLabel; keywords: readonly string[] }> = [
  {
    label: "Restricted",
    keywords: ["kyc", "beneficial ownership", "credit memo", "suitability", "application packet", "sar"],
  },
  {
    label: "Confidential",
    keywords: ["statement", "payment history", "credit review", "investment profile", "enrollment"],
  },
];

const CLASSIFICATIONS: Record<ClassificationLabel, Omit<Classification, "label">> = {
  Restricted: {
    guidance: "Do not share outside the deal team. Downloads are logged.",
    chipClassName: "bg-red-50 text-red-700 border-red-200",
  },
  Confidential: {
    guidance: "Share only with named colleagues who need it.",
    chipClassName: "bg-amber-50 text-amber-800 border-amber-200",
  },
  Internal: {
    guidance: "For Bank of America employees only.",
    chipClassName: "bg-blue-50 text-blue-700 border-blue-200",
  },
};

// Filename separators (space, _, -, ., etc.) become spaces so multiword phrases match however
// they are joined; keywords then have to start and end on a letter boundary so short ones
// like "sar" don't fire inside "Saratoga".
const normalize = (fileName: string) => fileName.toLowerCase().replace(/[^a-z0-9]+/g, " ");

const matchesKeyword = (fileName: string, keyword: string) =>
  new RegExp(`(?<![a-z])${keyword}(?![a-z])`).test(normalize(fileName));

export function classifyFile(fileName: string): Classification {
  const rule = RULES.find((r) => r.keywords.some((k) => matchesKeyword(fileName, k)));
  const label: ClassificationLabel = rule?.label ?? "Internal";
  return { label, ...CLASSIFICATIONS[label] };
}
