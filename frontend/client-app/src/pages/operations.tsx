import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { apiClient } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";

const chaosStateKey = "ow_admin_chaos_state";
const scenarios = [
  { service: "search-service", scenario: "suggest_500" },
  { service: "file-service", scenario: "upload_s3_error" },
  { service: "notification-service", scenario: "consumer_strict_schema" },
  { service: "document-service", scenario: "slow_queries" },
];
const services = ["api-gateway", "auth-service", "file-service", "document-service", "collab-service", "notification-service", "search-service", "analytics-service", "admin-service", "audit-service", "report-service"];
const buttonClass = "rounded bg-[#012169] px-4 py-2 text-sm font-medium text-white hover:bg-[#003b80] disabled:opacity-50";
const inputClass = "mt-1 w-full rounded border border-gray-300 p-2 text-gray-900";

interface Incident {
  id: string;
  title: string;
  description: string;
  severity: string;
  status: string;
  active: boolean;
  devinSessionId: string | null;
  devinSessionUrl: string | null;
  devinSessionStatus: string | null;
}

function loadChaosState(): Record<string, boolean> {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(chaosStateKey) || "{}");
    if (stored && typeof stored === "object" && !Array.isArray(stored)) {
      return Object.fromEntries(Object.entries(stored).filter(([, value]) => value === true));
    }
  } catch { /* Ignore invalid or unavailable browser storage. */ }
  return {};
}

export default function OperationsPage() {
  const { isAuthenticated, isLoading } = useAuthStore();
  if (isLoading) return <p role="status" className="p-6">Loading Operations Console…</p>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <AppShell><OperationsContent /></AppShell>;
}

function OperationsContent() {
  const queryClient = useQueryClient();
  const [chaosState, setChaosState] = useState(loadChaosState);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState("high");
  const [affectedService, setAffectedService] = useState("");
  // apiClient maps response keys (including Devin session fields) to camelCase.
  const incidents = useQuery({
    queryKey: ["admin", "incidents"],
    queryFn: async () => (await apiClient.get<{ incidents: Incident[] }>("/admin/incidents")).data.incidents,
    refetchInterval: 10000,
  });

  async function perform(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try { await action(); }
    catch { setError("Operation failed. Check your admin permissions and try again."); }
    finally { setBusy(false); }
  }

  function saveChaosState(state: Record<string, boolean>) {
    setChaosState(state);
    try { localStorage.setItem(chaosStateKey, JSON.stringify(state)); }
    catch { setError("Chaos updated, but the active state could not be saved in this browser."); }
  }

  function createIncident(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !description.trim()) return;
    void perform(async () => {
      await apiClient.post("/admin/incidents", { incident: { title, description, severity, affected_service: affectedService } });
      setTitle("");
      setDescription("");
      setSeverity("high");
      setAffectedService("");
      await queryClient.invalidateQueries({ queryKey: ["admin", "incidents"] });
    });
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><h1 className="text-2xl font-bold text-[#012169]">Operations Console</h1><p className="mt-1 text-sm text-gray-600">Incident response and demo controls. Admin access required.</p></div>
        <nav aria-label="Observability" className="flex gap-4 text-sm text-[#012169] underline">
          <a href="https://grafana.otterworks.app/d/bofa-incidents" target="_blank" rel="noopener noreferrer">Grafana</a>
          <a href="https://jaeger.otterworks.app" target="_blank" rel="noopener noreferrer">Jaeger</a>
        </nav>
      </div>
      {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-red-800">{error}</p>}
      <section className="rounded border border-gray-200 bg-white p-5" aria-labelledby="chaos-heading">
        <h2 id="chaos-heading" className="text-lg font-semibold text-[#012169]">Chaos controls</h2>
        <p className="mt-1 text-sm text-gray-600">Inject failures to exercise incident response. Flags auto-reset after 10 minutes; indicators reflect this browser&apos;s last actions.</p>
        <div className="my-4 grid gap-4 sm:grid-cols-2">
          {scenarios.map(({ service, scenario }) => (
            <div key={service} className="rounded border border-gray-200 p-4">
              <h3 className="font-medium text-gray-900">{service}</h3>
              <button className={`${buttonClass} mt-3`} disabled={busy} aria-pressed={!!chaosState[service]} onClick={() => void perform(async () => {
                await apiClient.post("/admin/chaos", { service, scenario });
                saveChaosState({ ...chaosState, [service]: true });
              })}>{scenario}</button>
              {chaosState[service] && <p className="mt-2 text-sm font-semibold text-[#012169]">Active (last triggered here)</p>}
            </div>
          ))}
        </div>
        <button className={buttonClass} disabled={busy} onClick={() => void perform(async () => {
          await apiClient.delete("/admin/chaos");
          saveChaosState({});
          await queryClient.invalidateQueries({ queryKey: ["admin", "incidents"] });
        })}>Reset all</button>
      </section>
      <section aria-labelledby="incidents-heading" className="space-y-3">
        <h2 id="incidents-heading" className="text-lg font-semibold text-[#012169]">Incidents</h2>
        {incidents.isLoading && <p role="status">Loading incidents…</p>}
        {incidents.isError && <p role="alert">Failed to load incidents. <button className="underline" onClick={() => void incidents.refetch()}>Retry</button></p>}
        {incidents.data?.length === 0 && <p className="rounded border bg-white p-5 text-gray-600">No incidents reported.</p>}
        {incidents.data?.map((incident) => (
          <article key={incident.id} className="space-y-3 rounded border border-gray-200 bg-white p-5">
            <h3 className="font-semibold text-gray-900">{incident.title}</h3>
            <p className="text-sm text-gray-600">Severity: {incident.severity} · Status: {incident.status}</p>
            <p className="text-sm text-gray-700">{incident.description}</p>
            {incident.devinSessionStatus && <p className="text-sm">Devin session: {incident.devinSessionStatus}</p>}
            {incident.devinSessionUrl && /^https?:\/\//i.test(incident.devinSessionUrl) && <a className="block text-sm text-[#012169] underline" href={incident.devinSessionUrl} target="_blank" rel="noopener noreferrer">View Devin session</a>}
            {incident.active && !incident.devinSessionId && <button className={buttonClass} disabled={busy} onClick={() => void perform(async () => {
              await apiClient.post(`/admin/incidents/${encodeURIComponent(incident.id)}/trigger_session`, {});
              await queryClient.invalidateQueries({ queryKey: ["admin", "incidents"] });
            })}>Launch Devin</button>}
          </article>
        ))}
      </section>
      <form onSubmit={createIncident} className="space-y-4 rounded border border-gray-200 bg-white p-5">
        <h2 className="text-lg font-semibold text-[#012169]">Create incident</h2>
        <label className="block text-sm">Title<input required className={inputClass} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label className="block text-sm">Description<textarea required className={inputClass} value={description} onChange={(event) => setDescription(event.target.value)} /></label>
        <label className="block text-sm">Severity<select className={inputClass} value={severity} onChange={(event) => setSeverity(event.target.value)}>{["low", "medium", "high", "critical"].map((value) => <option key={value}>{value}</option>)}</select></label>
        <label className="block text-sm">Affected service<select className={inputClass} value={affectedService} onChange={(event) => setAffectedService(event.target.value)}><option value="">None</option>{services.map((service) => <option key={service}>{service}</option>)}</select></label>
        <button className={buttonClass} disabled={busy || !title.trim() || !description.trim()}>Create incident</button>
      </form>
    </div>
  );
}
