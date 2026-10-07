import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  billingApi,
  type RatingFinalization,
  type UsageRating,
  type UsageSummaryRow,
} from "./api";
import { BillingAlert } from "./alert";

const UUID = /^[0-9a-f-]{36}$/i;
const PERIOD_START = "2026-02-01";
const PERIOD_END = "2026-02-28";

export default function BillingUsageRatingPage() {
  const { tenantId } = useParams();
  const navigate = useNavigate();
  const [rating, setRating] = useState<UsageRating | null>(null);
  const [summary, setSummary] = useState<UsageSummaryRow[]>([]);
  const [finalized, setFinalized] = useState<RatingFinalization | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let mounted = true;
    setError("");
    setRating(null);
    setSummary([]);
    setFinalized(null);
    setIsLoading(true);
    if (!tenantId || !UUID.test(tenantId)) {
      setError("A valid tenant id is required.");
      setIsLoading(false);
      return () => {
        mounted = false;
      };
    }
    Promise.all([
      billingApi.usageRating(tenantId, PERIOD_START, PERIOD_END),
      billingApi.usageSummary(tenantId, PERIOD_START, PERIOD_END),
    ])
      .then(([ratingValue, summaryValue]) => {
        if (!mounted) return;
        setRating(ratingValue);
        setSummary(summaryValue);
      })
      .catch(() => {
        if (mounted) setError("The usage rating could not be loaded.");
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [tenantId, retry]);

  const finalize = () => {
    if (!tenantId || isFinalizing) return;
    setError("");
    setIsFinalizing(true);
    billingApi
      .finalizeRating(tenantId, PERIOD_START, PERIOD_END)
      .then(setFinalized)
      .catch(() => setError("The rating could not be finalized."))
      .finally(() => setIsFinalizing(false));
  };

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <button
        type="button"
        onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/billing/plans"))}
        className="text-sm text-otter-700 hover:underline"
      >
        Back
      </button>
      <h1 className="text-3xl font-bold">Usage rating</h1>
      <p className="text-sm text-gray-600">
        Period {PERIOD_START} to {PERIOD_END}
      </p>
      {error && <BillingAlert message={error} onDismiss={() => setError("")} />}
      {error && !rating && (
        <button
          type="button"
          onClick={() => setRetry((value) => value + 1)}
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
        >
          Retry
        </button>
      )}
      {isLoading && <p role="status">Loading usage rating…</p>}
      {!isLoading && rating && (
        <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm" aria-label="Usage rating">
          <dl className="grid gap-3 sm:grid-cols-2">
            <div><dt className="text-sm text-gray-500">Used units</dt><dd>{rating.used_units}</dd></div>
            <div><dt className="text-sm text-gray-500">Included units</dt><dd>{rating.quota_units}</dd></div>
            <div><dt className="text-sm text-gray-500">Rollover applied</dt><dd>{rating.rollover_units}</dd></div>
            <div><dt className="text-sm text-gray-500">Billable units</dt><dd>{rating.billable_units}</dd></div>
            <div><dt className="text-sm text-gray-500">First tier units</dt><dd>{rating.first_tier_units}</dd></div>
            <div><dt className="text-sm text-gray-500">Second tier units</dt><dd>{rating.second_tier_units}</dd></div>
            <div><dt className="text-sm text-gray-500">Overage amount</dt><dd>{rating.overage_amount}</dd></div>
          </dl>
          <button
            type="button"
            onClick={finalize}
            disabled={isFinalizing}
            className="mt-6 rounded-lg bg-otter-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {isFinalizing ? "Finalizing…" : "Finalize period"}
          </button>
        </section>
      )}
      {!isLoading && rating && (
        <section aria-label="Usage summary" className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold">Usage by kind</h2>
          {summary.length === 0 ? (
            <p className="mt-3">No usage in this period.</p>
          ) : (
            <table className="mt-3 w-full text-left text-sm">
              <thead>
                <tr><th>Kind</th><th>Events</th><th>Units</th></tr>
              </thead>
              <tbody>
                {summary.map((row) => (
                  <tr key={row.kind}>
                    <td>{row.kind}</td>
                    <td>{row.event_count}</td>
                    <td>{row.units}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
      {finalized && (
        <section aria-label="Finalized rating" className="rounded-xl border border-green-200 bg-green-50 p-6 text-sm">
          <p className="font-semibold">Period finalized</p>
          <p>
            Stored rollover {finalized.rollover_units}, billable {finalized.billable_units},
            overage {finalized.overage_amount}
          </p>
        </section>
      )}
    </main>
  );
}
