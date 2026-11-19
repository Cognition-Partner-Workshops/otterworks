import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { billingApi, type Entitlement } from "./api";
import { BillingAlert } from "./alert";
import { localToday } from "./format";
import { BillingDateInput, isCompleteDate } from "./date-input";

const UUID = /^[0-9a-f-]{36}$/i;

export default function BillingEntitlementPage() {
  const { tenantId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedDate = searchParams.get("on") ?? "";
  const asOf = isCompleteDate(requestedDate) ? requestedDate : localToday();
  const [entitlement, setEntitlement] = useState<Entitlement | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let mounted = true;
    setError("");
    setEntitlement(null);
    setIsLoading(true);
    if (!tenantId || !UUID.test(tenantId)) {
      setError("A valid tenant id is required.");
      setIsLoading(false);
      return () => {
        mounted = false;
        setError("");
      };
    }
    billingApi
      .entitlement(tenantId, asOf)
      .then((value) => {
        if (mounted) setEntitlement(value);
      })
      .catch(() => {
        if (mounted) setError("The entitlement could not be loaded.");
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });
    return () => {
      mounted = false;
      setError("");
    };
  }, [tenantId, asOf, retry]);

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <button
        type="button"
        onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/billing/plans"))}
        className="text-sm text-otter-700 hover:underline"
      >
        Back
      </button>
      <h1 className="text-3xl font-bold">Tenant entitlement</h1>
      <div>
        <label htmlFor="entitlement-as-of" className="mb-1 block text-sm font-medium">As of</label>
        <BillingDateInput
          id="entitlement-as-of"
          value={asOf}
          onChange={(value) => {
            const next = new URLSearchParams(searchParams);
            next.set("on", value);
            setSearchParams(next, { replace: true });
          }}
        />
      </div>
      {error && <BillingAlert message={error} onDismiss={() => setError("")} />}
      {error && (
        <button
          type="button"
          onClick={() => {
            setError("");
            setIsLoading(true);
            setRetry((value) => value + 1);
          }}
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
        >
          Retry
        </button>
      )}
      {isLoading && <p role="status">Loading entitlement…</p>}
      {!isLoading && !error && !entitlement && <p>No entitlement found.</p>}
      {!isLoading && entitlement && (
        <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm" aria-label="Tenant entitlement">
          <p className="text-sm text-gray-600">Tenant {entitlement.tenant_id}</p>
          <h2 className="mt-2 text-2xl font-semibold">{entitlement.plan_code}</h2>
          <dl className="mt-5 grid gap-3 sm:grid-cols-2">
            <div><dt className="text-sm text-gray-500">Tier</dt><dd>{entitlement.tier}</dd></div>
            <div><dt className="text-sm text-gray-500">Status</dt><dd>{entitlement.subscription_status}</dd></div>
            <div><dt className="text-sm text-gray-500">Included units</dt><dd>{entitlement.included_units}</dd></div>
            <div><dt className="text-sm text-gray-500">Effective on</dt><dd>{entitlement.effective_on}</dd></div>
          </dl>
          <Link
            to={`/billing/change/${entitlement.tenant_id}`}
            className="mt-6 inline-block rounded-lg bg-otter-600 px-3 py-2 text-sm font-semibold text-white"
          >
            Change plan
          </Link>
        </section>
      )}
    </main>
  );
}
