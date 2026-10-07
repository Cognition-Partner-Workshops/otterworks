import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  billingApi,
  type InvoiceLine,
  type InvoicePreviewLine,
  type IssuedInvoice,
} from "./api";
import { BillingAlert } from "./alert";

const UUID = /^[0-9a-f-]{36}$/i;
const PERIOD_START = "2026-02-01";
const PERIOD_END = "2026-02-28";

export default function BillingInvoicePage() {
  const { tenantId } = useParams();
  const navigate = useNavigate();
  const [preview, setPreview] = useState<InvoicePreviewLine[]>([]);
  const [issued, setIssued] = useState<IssuedInvoice | null>(null);
  const [lines, setLines] = useState<InvoiceLine[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isIssuing, setIsIssuing] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const issueRequest = useRef(0);

  useEffect(() => {
    let mounted = true;
    issueRequest.current += 1;
    setIsIssuing(false);
    setError("");
    setPreview([]);
    setIssued(null);
    setLines([]);
    setIsLoading(true);
    if (!tenantId || !UUID.test(tenantId)) {
      setError("A valid tenant id is required.");
      setIsLoading(false);
      return () => {
        mounted = false;
      };
    }
    billingApi
      .invoicePreview(tenantId, PERIOD_START, PERIOD_END)
      .then((value) => {
        if (mounted) setPreview(value);
      })
      .catch(() => {
        if (mounted) setError("The invoice preview could not be loaded.");
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [tenantId, retry]);

  const issue = () => {
    if (!tenantId || isIssuing) return;
    setError("");
    setIsIssuing(true);
    const request = ++issueRequest.current;
    const isCurrent = () => issueRequest.current === request;
    billingApi
      .issueInvoice(tenantId, PERIOD_START, PERIOD_END)
      .then(async (value) => {
        if (!isCurrent()) return;
        setIssued(value);
        const stored = await billingApi.invoiceLines(value.invoice_id);
        if (isCurrent()) setLines(stored);
      })
      .catch(() => {
        if (isCurrent()) setError("The invoice could not be issued.");
      })
      .finally(() => {
        if (isCurrent()) setIsIssuing(false);
      });
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
      <h1 className="text-3xl font-bold">Invoice</h1>
      <p className="text-sm text-gray-600">
        Period {PERIOD_START} to {PERIOD_END}
      </p>
      {error && <BillingAlert message={error} onDismiss={() => setError("")} />}
      {error && preview.length === 0 && (
        <button
          type="button"
          onClick={() => setRetry((value) => value + 1)}
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
        >
          Retry
        </button>
      )}
      {isLoading && <p role="status">Loading invoice preview…</p>}
      {!isLoading && preview.length > 0 && (
        <section aria-label="Invoice preview" className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <table className="w-full text-left text-sm">
            <thead>
              <tr><th>Line</th><th>Type</th><th>Description</th><th>Amount</th><th>Credit</th><th>Total</th></tr>
            </thead>
            <tbody>
              {preview.map((line) => (
                <tr key={line.line_no}>
                  <td>{line.line_no}</td>
                  <td>{line.line_type}</td>
                  <td>{line.description}</td>
                  <td>{line.amount}</td>
                  <td>{line.credit_applied}</td>
                  <td>{line.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            type="button"
            onClick={issue}
            disabled={isIssuing}
            className="mt-6 rounded-lg bg-otter-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {isIssuing ? "Issuing…" : "Issue invoice"}
          </button>
        </section>
      )}
      {issued && (
        <section aria-label="Issued invoice" className="rounded-xl border border-green-200 bg-green-50 p-6 text-sm">
          <p className="font-semibold">Invoice {issued.status}</p>
          <p>
            Subtotal {issued.subtotal}, tax {issued.tax}, total {issued.total}
          </p>
          {lines.length > 0 && (
            <ul className="mt-3 list-disc pl-5">
              {lines.map((line) => (
                <li key={line.line_no}>
                  {line.description}: {line.amount}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  );
}
