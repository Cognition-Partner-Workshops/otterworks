import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  billingApi,
  BillingApiError,
  type FinalizedRating,
  type RatingPeriod,
  type RatingResult,
  type UsageRating,
  type UsageSummary,
} from "./api";
import { BillingAlert } from "./alert";

type Selection = RatingPeriod & { tenantId: string };

const DEFAULT_SELECTION: Selection = {
  tenantId: "00000000-0000-0000-0000-000000000001",
  period_start: "2026-02-01",
  period_end: "2026-02-28",
};
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const INPUT_CLASS = "w-full rounded-lg border border-gray-300 px-3 py-2";

function requestError(error: unknown, action: string): string {
  const status = error instanceof BillingApiError ? ` (HTTP ${error.status})` : "";
  return `${action}${status}.`;
}

function ResultDetails({ result }: Readonly<{ result: RatingResult }>) {
  return (
    <dl className="grid gap-4 sm:grid-cols-3">
      <div><dt className="text-sm text-gray-500">Used units</dt><dd>{result.used_units}</dd></div>
      <div><dt className="text-sm text-gray-500">Quota units</dt><dd>{result.quota_units}</dd></div>
      <div><dt className="text-sm text-gray-500">Rollover units</dt><dd>{result.rollover_units}</dd></div>
      <div><dt className="text-sm text-gray-500">Billable units</dt><dd>{result.billable_units}</dd></div>
      <div><dt className="text-sm text-gray-500">Overage amount</dt><dd>${result.overage_amount}</dd></div>
    </dl>
  );
}

export default function BillingRatingPage() {
  const [selection, setSelection] = useState(DEFAULT_SELECTION);
  const [rating, setRating] = useState<UsageRating | null>(null);
  const [summary, setSummary] = useState<UsageSummary[]>([]);
  const [persisted, setPersisted] = useState<FinalizedRating | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const requestVersion = useRef(0);

  const loadRating = useCallback((submitted: Selection) => {
    const version = ++requestVersion.current;
    const isCurrent = () => version === requestVersion.current;
    setError("");
    setRating(null);
    setSummary([]);
    setPersisted(null);
    if (!UUID.test(submitted.tenantId) || !submitted.period_start || !submitted.period_end ||
        submitted.period_end < submitted.period_start) {
      setError("Enter a valid tenant id and a period whose end is on or after its start.");
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    const period = { period_start: submitted.period_start, period_end: submitted.period_end };
    Promise.all([
      billingApi.rating(submitted.tenantId, period),
      billingApi.usageSummary(submitted.tenantId, period),
    ])
      .then(([nextRating, nextSummary]) => {
        if (isCurrent()) {
          setRating(nextRating);
          setSummary(nextSummary);
        }
      })
      .catch((error: unknown) => {
        if (isCurrent()) setError(requestError(error, "Rating and usage summary could not be loaded"));
      })
      .finally(() => {
        if (isCurrent()) setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    loadRating(DEFAULT_SELECTION);
    return () => { requestVersion.current += 1; };
  }, [loadRating]);

  const changeSelection = (field: keyof Selection, value: string) => {
    requestVersion.current += 1;
    setSelection((current) => ({ ...current, [field]: value }));
    setRating(null);
    setSummary([]);
    setPersisted(null);
    setError("");
    setIsLoading(false);
  };

  const finalize = () => {
    if (!rating || isSaving) return;
    const version = ++requestVersion.current;
    const isCurrent = () => version === requestVersion.current;
    setError("");
    setPersisted(null);
    setIsSaving(true);
    billingApi.finalizeRating(selection.tenantId, {
      period_start: selection.period_start,
      period_end: selection.period_end,
    })
      .then((result) => { if (isCurrent()) setPersisted(result); })
      .catch((error: unknown) => {
        if (isCurrent()) setError(requestError(error, "Rating could not be finalized"));
      })
      .finally(() => { if (isCurrent()) setIsSaving(false); });
  };

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-otter-600">Billing</p>
          <h1 className="text-3xl font-bold text-gray-900">Usage rating</h1>
        </div>
        <Link to="/billing/plans" className="text-sm text-otter-700 hover:underline">View plans</Link>
      </header>
      {error && <BillingAlert message={error} onDismiss={() => setError("")} />}
      <form onSubmit={(event) => { event.preventDefault(); loadRating(selection); }}>
        <fieldset disabled={isSaving} className="space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <legend className="sr-only">Rating period</legend>
          <div>
            <label htmlFor="rating-tenant" className="mb-1 block text-sm font-medium">Tenant id</label>
            <input id="rating-tenant" required value={selection.tenantId}
              onChange={(event) => changeSelection("tenantId", event.target.value)} className={INPUT_CLASS} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="rating-start" className="mb-1 block text-sm font-medium">Period start</label>
              <input id="rating-start" type="date" required value={selection.period_start}
                onChange={(event) => changeSelection("period_start", event.target.value)} className={INPUT_CLASS} />
            </div>
            <div>
              <label htmlFor="rating-end" className="mb-1 block text-sm font-medium">Period end</label>
              <input id="rating-end" type="date" required value={selection.period_end}
                onChange={(event) => changeSelection("period_end", event.target.value)} className={INPUT_CLASS} />
            </div>
          </div>
          <button type="submit" disabled={isLoading}
            className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm disabled:opacity-50">
            Load rating
          </button>
        </fieldset>
      </form>
      {isLoading && <p role="status">Loading rating and usage summary…</p>}
      {rating && (
        <>
          <section aria-label="Usage rating result" className="space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold">Rating result</h2>
            <ResultDetails result={rating} />
            <dl className="grid gap-4 sm:grid-cols-3">
              <div><dt className="text-sm text-gray-500">First-tier units</dt><dd>{rating.first_tier_units}</dd></div>
              <div><dt className="text-sm text-gray-500">Second-tier units</dt><dd>{rating.second_tier_units}</dd></div>
            </dl>
            <p className="text-sm text-gray-600">Rollover above is the credit applied. Finalizing stores unused quota for future periods.</p>
            <button type="button" disabled={isSaving} onClick={finalize}
              className="rounded-lg bg-otter-600 px-4 py-2 font-semibold text-white disabled:opacity-50">
              {isSaving ? "Finalizing…" : "Finalize rating"}
            </button>
          </section>
          <section aria-label="Usage summary" className="space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold">Usage summary</h2>
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Usage by kind</caption>
              <thead><tr><th scope="col">Kind</th><th scope="col">Events</th><th scope="col">Units</th></tr></thead>
              <tbody>
                {summary.map((row) => <tr key={row.kind} className="border-t border-gray-100">
                  <th scope="row" className="py-3 font-medium">{row.kind}</th><td>{row.event_count}</td><td>{row.units}</td>
                </tr>)}
                {summary.length === 0 && <tr><td colSpan={3} className="py-3 text-gray-600">No usage events in this period.</td></tr>}
              </tbody>
            </table>
          </section>
        </>
      )}
      {persisted && (
        <section aria-label="Persisted rating result" className="space-y-4 rounded-xl border border-green-200 bg-green-50 p-6">
          <h2 className="text-xl font-semibold">Persisted rating result</h2>
          <p role="status">Rating finalized for {selection.period_start} through {selection.period_end}.</p>
          {persisted.rating_result.map((row, index) => <ResultDetails key={index} result={row} />)}
        </section>
      )}
    </main>
  );
}
