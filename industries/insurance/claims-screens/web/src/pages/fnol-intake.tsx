import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type FnolResult } from "../api";
import { ErrorNote, Evidence, Field, Outcome, Panel } from "../ui";

export function FnolIntake() {
  const [fnols, setFnols] = useState<string[]>([]);
  const [claim, setClaim] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<FnolResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.fnols().then((r) => { setFnols(r.fnols); setClaim((c) => c || r.fnols[0] || ""); }).catch((e) => setError(String(e.message ?? e)));
  }, []);

  async function submit() {
    setBusy(true); setError(null); setResult(null);
    try { setResult(await api.submitFnol(claim)); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-4">
      <Panel title="First notice of loss">
        <p className="text-sm text-gray-600 mb-3">Submit an agency FNOL from the corpus (corpus/inputs/fnol) to the claims hub.</p>
        <form className="flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <label className="flex flex-col text-xs text-gray-600">
            Corpus FNOL
            <select aria-label="Corpus FNOL" value={claim} onChange={(e) => setClaim(e.target.value)}
              className="mt-1 w-64 border border-gray-300 rounded px-2 py-1.5 text-sm font-mono">
              {fnols.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
          <button disabled={!claim || busy} className="bg-otter-600 hover:bg-otter-700 disabled:opacity-50 text-white text-sm px-3 py-1.5 rounded">
            {busy ? "Waiting for the hub…" : "Submit FNOL"}
          </button>
        </form>
        <ErrorNote error={error} />
      </Panel>
      {result && (
        <Panel title="Intake result" aside={<Link className="text-sm text-otter-600 hover:underline" to={`/claims/${result.claimNumber}`}>Claim status →</Link>}>
          <dl>
            <Field label="Claim number"><span data-testid="claim-number" className="font-mono">{result.claimNumber}</span></Field>
            <Field label="Triage outcome"><Outcome value={result.outcome} /></Field>
            <Field label="FnolIntake instance">{result.fnolStatus}{result.statusReason ? ` — ${result.statusReason}` : ""}</Field>
            <Field label="Reasons">{result.reasons.length ? <ul className="list-disc ml-4">{result.reasons.map((r) => <li key={r}>{r}</li>)}</ul> : null}</Field>
          </dl>
          <Evidence items={result.evidence} />
        </Panel>
      )}
    </div>
  );
}
