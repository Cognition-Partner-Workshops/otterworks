import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  billingApi, BillingApiError, type Plan, type PlanChangeQuote,
  type CustomerPlanChangeResult, type CustomerPlan, type Invoice, type InvoiceLine,
} from "./api";
import { BillingAlert } from "./alert";
import { localToday, money, readableDate } from "./format";

const UUID = /^[0-9a-f-]{36}$/i;
const card = "space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm";

function Lines({ lines }: { lines: InvoiceLine[] }) {
  return (
    <table className="w-full text-left text-sm">
      <thead><tr><th className="py-2">Description</th><th className="py-2 text-right">Amount</th></tr></thead>
      <tbody>{lines.map((line, index) => (
        <tr key={index} className="border-t border-gray-100">
          <td className="py-3 pr-4">{line.description}</td>
          <td className="py-3 text-right tabular-nums">{money(line.amount)}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}

function InvoiceDetails({ invoice }: { invoice: Invoice }) {
  return <>
    <p>{invoice.summary}</p>
    <p className="text-sm text-gray-600">Issued {readableDate(invoice.issued_on)}</p>
    <Lines lines={invoice.lines} />
    <p className="text-right font-semibold">Total: {money(invoice.total)}</p>
  </>;
}

export default function BillingChangePlanPage() {
  const { tenantId = "" } = useParams();
  const [searchParams] = useSearchParams();
  return <ChangePlan key={tenantId} tenantId={tenantId} preselect={searchParams.get("plan") ?? ""} />;
}

function ChangePlan({ tenantId, preselect }: { tenantId: string; preselect: string }) {
  const navigate = useNavigate();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [planId, setPlanId] = useState(preselect);
  const [changeDate, setChangeDate] = useState(localToday);
  const [currentPlan, setCurrentPlan] = useState<CustomerPlan | null>(null);
  const [quote, setQuote] = useState<PlanChangeQuote | null>(null);
  const [result, setResult] = useState<CustomerPlanChangeResult | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isQuoting, setIsQuoting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [invoiceError, setInvoiceError] = useState("");
  const [retry, setRetry] = useState(0);
  const requestVersion = useRef(0);
  const invoiceVersion = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setError("");
    setInvoiceError("");
    setIsLoading(true);
    if (!UUID.test(tenantId)) {
      setError("A valid tenant id is required.");
      setIsLoading(false);
      return;
    }
    billingApi.listPlans().then((items) => {
      if (active) setPlans(items);
    }).catch(() => {
      if (active) setError("Plans could not be loaded.");
    }).finally(() => {
      if (active) setIsLoading(false);
    });
    const version = ++invoiceVersion.current;
    billingApi.listInvoices(tenantId).then((items) => {
      if (active && version === invoiceVersion.current) setInvoices(items);
    }).catch((error: unknown) => {
      if (active && version === invoiceVersion.current) setInvoiceError(error instanceof BillingApiError ? error.message : "Invoices could not be loaded.");
    });
    return () => { active = false; };
  }, [tenantId, retry]);

  useEffect(() => {
    let active = true;
    let quoted = false;
    ++requestVersion.current;
    setQuote(null);
    setCurrentPlan(null);
    setIsQuoting(false);
    if (!UUID.test(tenantId) || !changeDate) return;
    setError("");
    billingApi.entitlement(tenantId, changeDate).then((item) => {
      if (active && !quoted) setCurrentPlan({ code: item.plan_code, name: item.plan_code.charAt(0) + item.plan_code.slice(1).toLowerCase(), monthly_fee: item.monthly_fee });
    }).catch((error: unknown) => {
      if (active && !planId) setError(error instanceof BillingApiError ? error.message : "Current plan could not be loaded.");
    });
    if (planId) {
      setIsQuoting(true);
      billingApi.quotePlanChange(tenantId, planId, changeDate).then((value) => {
        if (active) { quoted = true; setQuote(value); setCurrentPlan(value.current_plan); }
      }).catch((error: unknown) => {
        if (active) setError(error instanceof BillingApiError ? error.message : "The quote could not be loaded.");
      }).finally(() => {
        if (active) setIsQuoting(false);
      });
    }
    return () => { active = false; };
  }, [tenantId, planId, changeDate, retry]);

  const invalidate = () => {
    ++requestVersion.current;
    setQuote(null);
    setResult(null);
    setError("");
    setIsSaving(false);
  };

  const submit = async () => {
    if (!quote || isSaving || result) return;
    const version = ++requestVersion.current;
    const isCurrent = () => mounted.current && version === requestVersion.current;
    setResult(null);
    setError("");
    setIsSaving(true);
    try {
      const value = await billingApi.applyPlanChange(tenantId, planId, changeDate);
      if (!isCurrent()) return;
      setResult(value);
      setQuote(null);
      setCurrentPlan(value.kind === "upgrade" ? value.new_plan : value.current_plan);
      if (value.kind === "upgrade") {
        const invoiceRequest = ++invoiceVersion.current;
        try {
          const items = await billingApi.listInvoices(tenantId);
          if (isCurrent() && invoiceRequest === invoiceVersion.current) { setInvoices(items); setInvoiceError(""); }
        } catch {
          if (isCurrent()) setInvoiceError("Your change was saved, but invoices could not be refreshed.");
        }
      }
    } catch (error: unknown) {
      if (isCurrent()) setError(error instanceof BillingApiError ? error.message : "The plan change could not be saved.");
    } finally {
      if (isCurrent()) setIsSaving(false);
    }
  };

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <button type="button" onClick={() => window.history.length > 1 ? navigate(-1) : navigate("/billing/plans")} className="text-sm text-otter-700 hover:underline">Back</button>
      <h1 className="text-3xl font-bold">Change plan</h1>
      {error && <BillingAlert message={error} onDismiss={() => setError("")} />}
      {error && <button type="button" onClick={() => { invalidate(); setRetry((value) => value + 1); }} className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm">Retry</button>}
      {currentPlan && <p>Current plan: <strong>{currentPlan.name}</strong> · {money(currentPlan.monthly_fee)} / month</p>}
      {result?.kind === "downgrade" && <p>Scheduled change: {result.new_plan.name} starts on {readableDate(result.effective_on)}.</p>}
      {isLoading && <p role="status">Loading plans…</p>}
      {!isLoading && !error && plans.length === 0 && <p>No plans are available.</p>}
      {!isLoading && plans.length > 0 && (
        <form className={card} onSubmit={(event) => { event.preventDefault(); void submit(); }}>
          <div>
            <label htmlFor="billing-plan" className="mb-1 block text-sm font-medium">Plan</label>
            <select id="billing-plan" value={planId} onChange={(event) => { invalidate(); setPlanId(event.target.value); }} className="w-full rounded-lg border border-gray-300 px-3 py-2">
              <option value="">Choose a plan</option>
              {plans.map((plan) => <option key={plan.plan_id} value={plan.plan_id}>{plan.code.charAt(0) + plan.code.slice(1).toLowerCase()}{plan.code === currentPlan?.code ? " (current)" : ""} — {money(plan.monthly_fee)} / month</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="change-date" className="mb-1 block text-sm font-medium">Change date</label>
            <input id="change-date" type="date" value={changeDate} onChange={(event) => { invalidate(); setChangeDate(event.target.value); }} aria-describedby="date-help" className="w-full rounded-lg border border-gray-300 px-3 py-2" />
            <p id="date-help" className="mt-1 text-sm text-gray-500">Fixture simulation of today’s date.</p>
          </div>
          {isQuoting && <p role="status">Loading quote…</p>}
          {quote && <section aria-label="Plan change preview" className="space-y-4 rounded-lg bg-gray-50 p-4">
            <h2 className="text-xl font-semibold">{quote.kind === "upgrade" ? "Upgrade" : "Downgrade"}</h2>
            <p>{quote.summary}</p>
            {quote.kind === "upgrade" ? <>
              <p>Billing period: {readableDate(quote.cycle_start)} – {readableDate(quote.cycle_end)} ({quote.days_remaining} of {quote.days_in_cycle} days)</p>
              <Lines lines={quote.lines} />
              <p className="font-semibold">Due today: {money(quote.amount_due)}</p>
            </> : <>
              <p>Starts on {readableDate(quote.effective_on)}</p>
              <p className="font-semibold">$0.00 due today</p>
            </>}
          </section>}
          {!result && <button type="submit" disabled={!quote || isSaving || isQuoting} className="rounded-lg bg-otter-600 px-4 py-2 font-semibold text-white disabled:opacity-50">
            {isSaving ? "Saving…" : !quote ? "Choose a plan to continue" : quote.kind === "upgrade" ? `Upgrade now and pay ${money(quote.amount_due)}` : "Schedule downgrade"}
          </button>}
        </form>
      )}
      {result && <section aria-label="Plan change confirmation" className={`${card} bg-green-50`}>
        <h2 className="text-xl font-semibold">{result.kind === "upgrade" ? "Upgrade confirmed" : `Scheduled: ${result.new_plan.name} starts on ${readableDate(result.effective_on)}`}</h2>
        {result.invoice ? <InvoiceDetails invoice={result.invoice} /> : <p>$0.00 due today</p>}
      </section>}
      <section aria-label="Invoices" className={card}>
        <h2 className="text-xl font-semibold">Invoices</h2>
        {invoiceError && <BillingAlert message={invoiceError} onDismiss={() => setInvoiceError("")} />}
        {!invoiceError && invoices.length === 0 && <p>No adjustment invoices yet.</p>}
        {invoices.map((invoice) => <article key={invoice.id} className="space-y-3 border-t border-gray-200 pt-4"><InvoiceDetails invoice={invoice} /></article>)}
      </section>
    </main>
  );
}
