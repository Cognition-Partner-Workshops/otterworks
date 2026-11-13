import { Link, useParams } from "react-router-dom";
import { AppShell } from "@/components/layout/app-shell";

export const claimStatus: Record<number, string> = {
  1: "Reported",
  2: "Under review",
  3: "Reserved",
  4: "Approved",
  5: "Paid",
  6: "Denied",
  7: "Reopened",
};

const claims = Array.from({ length: 7 }, (_, index) => ({
  clm_id: index + 1,
  pol_id: index + 1,
  clm_status: index + 1,
  report_dt: "2025-06-17",
  pay_amt: 51 + index,
}));

export default function ClaimsPage() {
  const { id } = useParams();
  const claim = claims.find((row) => String(row.clm_id) === id);
  return (
    <AppShell>
      <h1 className="text-2xl font-semibold mb-4">Claims</h1>
      <p className="text-sm text-gray-600 mb-4">Commission Pay claims register (June 2025)</p>
      {id ? (
        claim ? (
          <section className="bg-white border rounded p-4" aria-label="Claim detail">
            <h2 className="text-lg font-semibold">Claim {claim.clm_id}</h2>
            <dl className="grid grid-cols-2 gap-2 my-4">
              <dt>Policy</dt><dd>{claim.pol_id}</dd>
              <dt>Status</dt><dd>{claimStatus[claim.clm_status] ?? "Unavailable"}</dd>
              <dt>Report date</dt><dd>{claim.report_dt}</dd>
              <dt>Payments (USD)</dt><dd>{claim.pay_amt.toFixed(2)}</dd>
            </dl>
            <Link to="/claims" className="text-otter-600 underline">Back to claims</Link>
          </section>
        ) : <p role="alert">Claim not found. <Link to="/claims">Back to claims</Link></p>
      ) : (
        <table className="w-full bg-white border text-left">
          <caption className="sr-only">Claims register</caption>
          <thead><tr><th className="p-3">Claim</th><th>Policy</th><th>Status</th><th>Payments (USD)</th></tr></thead>
          <tbody>{claims.map((row) => (
            <tr key={row.clm_id} className="border-t">
              <td className="p-3"><Link className="text-otter-600 underline" to={`/claims/${row.clm_id}`}>Claim {row.clm_id}</Link></td>
              <td>{row.pol_id}</td><td>{claimStatus[row.clm_status] ?? "Unavailable"}</td><td>{row.pay_amt.toFixed(2)}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </AppShell>
  );
}
