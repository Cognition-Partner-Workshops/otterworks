import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, cents, type Payment } from "../api";
import { ErrorNote, Evidence, Field, LookupForm, Panel } from "../ui";

export function PaymentConfirmation() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [query, setQuery] = useState(id ?? "");
  const [data, setData] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null); setError(null);
    if (id) { setQuery(id); api.payment(id).then(setData).catch((e) => setError(e.message)); }
  }, [id]);

  const remitted = new Map((data?.remittance?.lines ?? []).map((l) => [l.seq, l]));

  return (
    <div>
      <LookupForm label="Payment instruction" value={query} onChange={setQuery} onSubmit={() => navigate(`/payments/${query}`)} placeholder="PI-2026-880107" />
      <ErrorNote error={error} />
      {data && (
        <div className="space-y-4">
          <Panel title={`Payment ${data.instructionId}`}
            aside={<span data-testid="file-status" className="border border-otter-300 bg-otter-100 text-otter-800 px-2 py-0.5 text-sm font-semibold">{data.fileStatus.state}</span>}>
            <dl>
              <Field label="Instruction"><span className="font-mono">{data.instructionId}</span> · claim <span className="font-mono">{data.claimNumber}</span> · policy <span className="font-mono">{data.policyNumber}</span> · value date {data.valueDate}</Field>
              <Field label="Payee">{data.payee.name} ({data.payee.type}) · account {data.payee.account} · vendor {data.vendorCode}</Field>
              <Field label="Vendor reference"><span data-testid="vendor-reference" className="font-mono">{data.ledger?.vendorReference}</span></Field>
              <Field label="Ledger post">{data.ledger ? <>indemnity {data.ledger.indemnityAmount} · expense {data.ledger.expenseAmount} · salvage {data.ledger.salvageCredit} · net <strong data-testid="ledger-net">{data.ledger.netAmount}</strong> {data.currency}</> : null}</Field>
              <Field label="Remittance file">{data.remittance ? <><span className="font-mono">{data.remittance.fileName}</span> · {data.remittance.trailer?.count} lines · net <strong data-testid="file-net">{data.remittance.trailer ? cents(data.remittance.trailer.netCents) : "—"}</strong> {data.currency} · trailer {data.remittance.trailerMatchesLines ? "reconciles" : "does not reconcile"}</> : null}</Field>
              <Field label="File status">{data.fileStatus.detail}</Field>
            </dl>
          </Panel>
          <Panel title="Lines">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-gray-500 border-b border-gray-200">
                <tr><th className="py-1">#</th><th>Type</th><th>GL account</th><th>Memo</th><th className="text-right">Instructed</th><th className="text-right">Remitted</th></tr>
              </thead>
              <tbody>
                {data.lines.map((l) => {
                  const r = remitted.get(l.lineNo);
                  return (
                    <tr key={l.lineNo} className="border-b border-gray-100">
                      <td className="py-1">{l.lineNo}</td><td>{l.lineType}</td><td className="font-mono">{l.glAccount}</td><td>{l.memo}</td>
                      <td className="text-right font-mono">{l.amount}</td>
                      <td className="text-right font-mono">{r ? `${cents(r.amountCents)} ${r.direction}` : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Panel>
          {data.differences.map((d) => (
            <p key={d} data-testid="difference" className="border border-accent-500 bg-accent-400/20 px-3 py-2 text-sm text-gray-900">{d}</p>
          ))}
          <Evidence items={data.evidence} />
        </div>
      )}
    </div>
  );
}
