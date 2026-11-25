import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type ClaimStatus } from "../api";
import { ErrorNote, Evidence, Field, LookupForm, Outcome, Panel } from "../ui";

export function ClaimStatusPage() {
  const { claim } = useParams();
  const navigate = useNavigate();
  const [query, setQuery] = useState(claim ?? "");
  const [data, setData] = useState<ClaimStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null); setError(null);
    if (claim) { setQuery(claim); api.claim(claim).then(setData).catch((e) => setError(e.message)); }
  }, [claim]);

  return (
    <div>
      <LookupForm label="Claim number" value={query} onChange={setQuery} onSubmit={() => navigate(`/claims/${query}`)} placeholder="CLM-2026-100400" />
      <ErrorNote error={error} />
      {data && (
        <Panel title={`Claim ${data.claimNumber}`} aside={<Outcome value={data.outcome} />}>
          <dl>
            <Field label="Claim"><span className="font-mono">{data.claimNumber}</span> · {data.claimant} · {data.lossCause}</Field>
            <Field label="Policy">
              <span className="font-mono">{data.policy.number}</span> · {data.policy.lineOfBusiness} · {data.policy.status} since {data.policy.effectiveDate}
              {" "}· in force at loss: {data.policy.inForceAtLoss}
            </Field>
            <Field label="Outcome"><Outcome value={data.outcome} /> <span className="ml-2 text-gray-500">{data.fnolStatus}</span></Field>
            <Field label="Reasons">{data.reasons.length ? <ul className="list-disc ml-4">{data.reasons.map((r) => <li key={r}>{r}</li>)}</ul> : null}</Field>
            <Field label="Adjuster">
              {data.adjuster ? (
                <span>
                  {data.adjuster.name} (<span className="font-mono">{data.adjuster.id}</span>) · {data.adjuster.email}
                  {" "}· {data.adjuster.severity}, first contact within {data.adjuster.slaDays} day(s)
                  {data.adjuster.escalated ? " · escalated" : ""} · request <span className="font-mono">{data.adjuster.requestId}</span>
                </span>
              ) : <span className="text-gray-500">{data.missing.adjuster ?? "not assigned"}</span>}
            </Field>
          </dl>
          {Object.entries(data.missing).filter(([k]) => k !== "adjuster").map(([k, v]) => <p key={k} className="mt-2 text-xs text-gray-500">{v}</p>)}
          <Evidence items={data.evidence} />
        </Panel>
      )}
    </div>
  );
}
