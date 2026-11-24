export interface Source { source: "golden" | "camel"; label: string; detail: string }

export interface FnolResult {
  claimNumber: string;
  outcome: string | null;
  reasons: string[];
  fnolStatus: string | null;
  statusReason?: string | null;
  evidence: string[];
}

export interface Policy { number: string | null; status: string | null; lineOfBusiness: string | null; effectiveDate: string | null; inForceAtLoss: string | null }
export interface Adjuster { requestId: string; id: string | null; name: string | null; email: string | null; severity: string | null; slaDays: string | null; escalated: boolean }
export interface ClaimStatus extends FnolResult {
  claimant: string | null;
  lossCause: string | null;
  policy: Policy;
  adjuster: Adjuster | null;
  missing: Record<string, string>;
}

export interface RemittedLine { seq: number; lineType: string; amountCents: number; direction: string; glAccount: string }
export interface Payment {
  instructionId: string;
  claimNumber: string;
  policyNumber: string;
  vendorCode: string;
  valueDate: string;
  currency: string;
  payee: { name: string; type: string; account: string };
  lines: { lineNo: number; lineType: string; amount: string; glAccount: string | null; memo: string | null }[];
  ledger: { vendorReference: string | null; indemnityAmount: string | null; expenseAmount: string | null; salvageCredit: string | null; netAmount: string | null; lineCount: string | null } | null;
  remittance: { fileName: string; lines: RemittedLine[]; trailer: { count: number; netCents: number } | null; trailerMatchesLines: boolean } | null;
  fileStatus: { state: string; detail: string };
  differences: string[];
  evidence: string[];
}

async function call<T>(method: "GET" | "POST", path: string): Promise<T> {
  const res = await fetch(`/api/claims-screens${path}`, { method });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
  return body as T;
}

export const api = {
  source: () => call<Source>("GET", "/source"),
  fnols: () => call<{ fnols: string[] }>("GET", "/fnol"),
  submitFnol: (claim: string) => call<FnolResult>("POST", `/fnol/${encodeURIComponent(claim)}`),
  claim: (claim: string) => call<ClaimStatus>("GET", `/claims/${encodeURIComponent(claim)}`),
  payment: (id: string) => call<Payment>("GET", `/payments/${encodeURIComponent(id)}`),
};

export function cents(value: number): string {
  return (value / 100).toFixed(2);
}
