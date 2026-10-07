import { useRef, useState } from "react";
import {
  billingApi,
  BillingApiError,
  type DunningScheduleResult,
  type DunningSuspendResult,
  type OverdueAccount,
} from "./api";
import { BillingAlert } from "./alert";

type Action = "overdue" | "schedule" | "suspend";

export default function BillingDunningPage() {
  const [asOf, setAsOf] = useState("2026-02-28");
  const [accounts, setAccounts] = useState<OverdueAccount[] | null>(null);
  const [schedule, setSchedule] = useState<DunningScheduleResult | null>(null);
  const [suspension, setSuspension] = useState<DunningSuspendResult | null>(null);
  const [pending, setPending] = useState<Action | null>(null);
  const [error, setError] = useState("");
  const requestVersion = useRef(0);

  const run = <T,>(
    action: Action,
    call: () => Promise<T>,
    onSuccess: (value: T) => void,
    failure: string,
  ) => {
    if (!asOf) {
      setError("Choose an as-of date.");
      return;
    }
    const submittedVersion = ++requestVersion.current;
    const isCurrent = () => submittedVersion === requestVersion.current;
    setError("");
    setPending(action);
    call()
      .then((value) => {
        if (isCurrent()) onSuccess(value);
      })
      .catch((caught: unknown) => {
        if (!isCurrent()) return;
        setError(
          caught instanceof BillingApiError && caught.status === 409
            ? "Suspension was rolled back: a subscription starts after the as-of date."
            : failure,
        );
      })
      .finally(() => {
        if (isCurrent()) setPending(null);
      });
  };

  const buttonClass =
    "rounded-lg bg-otter-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50";

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6">
      <header>
        <p className="text-sm font-semibold uppercase tracking-wide text-otter-600">Billing</p>
        <h1 className="text-3xl font-bold text-gray-900">Dunning</h1>
      </header>
      {error && <BillingAlert message={error} onDismiss={() => setError("")} />}
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <div>
          <label htmlFor="dunning-as-of" className="mb-1 block text-sm font-medium">As of</label>
          <input
            id="dunning-as-of"
            type="date"
            value={asOf}
            onChange={(event) => setAsOf(event.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2"
          />
        </div>
        <button
          type="button"
          disabled={pending !== null}
          className={buttonClass}
          onClick={() =>
            run("overdue", () => billingApi.overdueAccounts(asOf), setAccounts, "Overdue accounts could not be loaded.")
          }
        >
          {pending === "overdue" ? "Loading…" : "List overdue accounts"}
        </button>
        <button
          type="button"
          disabled={pending !== null}
          className={buttonClass}
          onClick={() =>
            run("schedule", () => billingApi.scheduleDunning(asOf), setSchedule, "Dunning could not be scheduled.")
          }
        >
          {pending === "schedule" ? "Scheduling…" : "Schedule dunning"}
        </button>
        <button
          type="button"
          disabled={pending !== null}
          className={buttonClass}
          onClick={() =>
            run("suspend", () => billingApi.suspendOverdue(asOf), setSuspension, "Overdue tenants could not be suspended.")
          }
        >
          {pending === "suspend" ? "Suspending…" : "Suspend overdue tenants"}
        </button>
      </div>
      {accounts && (
        <section aria-label="Overdue accounts" className="space-y-2">
          <h2 className="text-xl font-semibold">Overdue accounts</h2>
          {accounts.length === 0 ? (
            <p className="text-gray-600">No accounts are overdue.</p>
          ) : (
            <ul className="space-y-1">
              {accounts.map((account) => (
                <li key={account.invoice_id}>
                  {account.tenant_id}: ${account.total}, {account.days_overdue} days overdue ({account.tenant_status})
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
      {schedule && (
        <section aria-label="Dunning attempts" className="space-y-2">
          <h2 className="text-xl font-semibold">Dunning attempts</h2>
          <p role="status">{schedule.scheduled.length} attempts scheduled.</p>
          <ul className="space-y-1">
            {schedule.attempts.map((attempt) => (
              <li key={`${attempt.invoice_id}-${attempt.attempt_no}`}>
                {attempt.invoice_id} attempt {attempt.attempt_no}: {attempt.scheduled_for} ({attempt.status})
              </li>
            ))}
          </ul>
        </section>
      )}
      {suspension && (
        <section aria-label="Suspensions" className="space-y-2">
          <h2 className="text-xl font-semibold">Suspensions</h2>
          <p role="status">{suspension.suspended_tenants.length} tenants suspended.</p>
          <ul className="space-y-1">
            {suspension.notifications.map((notification) => (
              <li key={notification.id}>
                {notification.tenant_id}: {notification.kind} notice sent {notification.sent_at}
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
