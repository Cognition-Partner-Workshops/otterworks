export const ACORD_FNOL_NS = "http://schemas.thistlecombe.example/acord/claims/fnol";

export const LOSS_CAUSES = [
  { code: "COLL", label: "Collision" },
  { code: "COMP", label: "Comprehensive (non-collision)" },
  { code: "GLAS", label: "Glass" },
  { code: "THFT", label: "Theft" },
  { code: "FIRE", label: "Fire" },
  { code: "WATR", label: "Water" },
  { code: "WIND", label: "Wind / hail" },
  { code: "LIAB", label: "Liability" },
] as const;

export type LossCauseCode = (typeof LOSS_CAUSES)[number]["code"];
export const LOSS_CAUSE_CODES = LOSS_CAUSES.map((c) => c.code) as LossCauseCode[];

export const LINES_OF_BUSINESS = ["AUTO", "HOME"] as const;
export type LineOfBusiness = (typeof LINES_OF_BUSINESS)[number];

// Producer recorded on notices that adjusters file from the app rather than
// through an agency feed.
export const MOBILE_PRODUCER = { id: "AG-MOBILE", name: "Thistlecombe field adjusters" };

export interface FnolDraft {
  policyNumber: string;
  lineOfBusiness: LineOfBusiness;
  givenName: string;
  surname: string;
  taxId?: string;
  lossDate: string;
  causeCode: LossCauseCode;
  description: string;
  estimatedLossAmt: string;
  injuries: boolean;
  city: string;
  stateProvCd: string;
  postalCode: string;
}

export interface FnolEnvelope {
  rqUID: string;
  transactionRequestDt: string;
  reportedDt: string;
  claimNumber: string;
  producer: { id: string; name: string };
}

/**
 * Same rule as the hub's PiiMaskingComponent.Mask(value, 4): walking from the
 * end, letters and digits after the fourth become X; separators are kept.
 */
export function maskTaxId(value: string, visible = 4): string {
  if (!value) return value;
  const chars = Array.from(value);
  let seen = 0;
  for (let i = chars.length - 1; i >= 0; i--) {
    if (!/[\p{L}\p{N}]/u.test(chars[i])) continue;
    seen++;
    if (seen > visible) chars[i] = "X";
  }
  return chars.join("");
}

export function lineOfBusinessFor(policyNumber: string): LineOfBusiness | undefined {
  const m = /^POL-([A-Z]+)-/.exec(policyNumber.trim().toUpperCase());
  return LINES_OF_BUSINESS.find((l) => l === m?.[1]);
}

/** "412" -> "412.00"; string-based so no float rounding touches the amount. */
export function normaliseAmount(value: string): string {
  const m = /^(\d+)(?:\.(\d{1,2}))?$/.exec(value.trim());
  if (!m) throw new Error(`Not a money amount: ${value}`);
  return `${m[1]}.${(m[2] ?? "").padEnd(2, "0")}`;
}

const pad = (n: number) => String(n).padStart(2, "0");
const localDate = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const localDateTime = (d: Date) =>
  `${localDate(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

export function newEnvelope(now = new Date(), uuid = () => crypto.randomUUID()): FnolEnvelope {
  const rqUID = uuid();
  return {
    rqUID,
    transactionRequestDt: localDateTime(now),
    reportedDt: localDate(now),
    claimNumber: `CLM-${now.getFullYear()}-M${rqUID.replace(/-/g, "").slice(0, 8).toUpperCase()}`,
    producer: MOBILE_PRODUCER,
  };
}

export function todayLocal(now = new Date()): string {
  return localDate(now);
}

function esc(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * ACORD ClaimsSvcRq / ClaimsNotificationAddRq as validated by
 * ACORD_ClaimsNotificationAddRq.xsd and read by Fnol_to_CanonicalClaim.
 * The tax id is masked here, so an unmasked value can never be serialised.
 */
export function buildClaimsSvcRq(draft: FnolDraft, env: FnolEnvelope): string {
  if (!LOSS_CAUSE_CODES.includes(draft.causeCode)) {
    throw new Error(`Unknown cause of loss: ${draft.causeCode}`);
  }
  const t = (name: string, value: string, indent: number) =>
    `${" ".repeat(indent)}<${name}>${esc(value)}</${name}>`;
  const taxId = draft.taxId?.trim();
  const lines = [
    `<ns0:ClaimsSvcRq xmlns:ns0="${ACORD_FNOL_NS}">`,
    t("RqUID", env.rqUID, 2),
    t("TransactionRequestDt", env.transactionRequestDt, 2),
    "  <ClaimsNotificationAddRq>",
    "    <Producer>",
    t("ProducerId", env.producer.id, 6),
    t("ProducerName", env.producer.name, 6),
    "    </Producer>",
    "    <Policy>",
    t("PolicyNumber", draft.policyNumber.trim().toUpperCase(), 6),
    t("LOBCd", draft.lineOfBusiness, 6),
    "    </Policy>",
    "    <InsuredOrPrincipal>",
    t("GivenName", draft.givenName.trim(), 6),
    t("Surname", draft.surname.trim(), 6),
    ...(taxId ? [t("TaxId", maskTaxId(taxId), 6)] : []),
    "    </InsuredOrPrincipal>",
    "    <ClaimsOccurrence>",
    t("ClaimNumber", env.claimNumber, 6),
    t("LossDt", draft.lossDate, 6),
    t("ReportedDt", env.reportedDt, 6),
    t("LossCauseCd", draft.causeCode, 6),
    t("IncidentDesc", draft.description, 6),
    t("EstimatedLossAmt", normaliseAmount(draft.estimatedLossAmt), 6),
    t("InjuryInd", String(draft.injuries), 6),
    "      <Addr>",
    t("City", draft.city.trim(), 8),
    t("StateProvCd", draft.stateProvCd.trim().toUpperCase(), 8),
    t("PostalCode", draft.postalCode.trim(), 8),
    "      </Addr>",
    "    </ClaimsOccurrence>",
    "  </ClaimsNotificationAddRq>",
    "</ns0:ClaimsSvcRq>",
  ];
  return lines.join("\n") + "\n";
}
