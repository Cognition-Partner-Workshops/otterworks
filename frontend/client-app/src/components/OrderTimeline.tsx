import type { Tracking } from "@/lib/types";

const fmt = (iso: string) => new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export function OrderTimeline({ tracking }: { tracking: Tracking }) {
  return (
    <section className="mt-8" aria-labelledby="tracking-heading" data-testid="order-timeline">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="tracking-heading" className="text-lg font-semibold">Order status</h2>
        {tracking.trackingNumber && (
          <p className="text-sm" data-testid="tracking-number">{tracking.carrier} tracking <span className="font-mono font-semibold">{tracking.trackingNumber}</span></p>
        )}
      </div>
      {tracking.estimatedArrival && <p className="mt-1 text-sm text-neutral-600">Estimated {tracking.steps.some((s) => s.code.startsWith("PICK")) ? "ready" : "arrival"}: <span className="font-semibold">{new Date(tracking.estimatedArrival).toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" })}</span></p>}
      <ol className="mt-4 grid gap-4 sm:grid-cols-[repeat(auto-fit,minmax(0,1fr))]">
        {tracking.steps.map((s, i) => {
          const current = s.code === tracking.currentStep;
          return (
            <li key={s.code} className="relative flex gap-3 sm:block" aria-current={current ? "step" : undefined} data-testid={`step-${s.code}`} data-done={s.done}>
              <div className="flex items-center sm:mb-2">
                <span className={`z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${s.done ? "bg-teal text-white" : "border-2 border-neutral-300 bg-white text-neutral-400"} ${current ? "ring-4 ring-teal/25" : ""}`} aria-hidden="true">
                  {s.done ? "✓" : i + 1}
                </span>
                {i < tracking.steps.length - 1 && <span className={`hidden h-0.5 flex-1 sm:block ${tracking.steps[i + 1].done ? "bg-teal" : "bg-neutral-300"}`} aria-hidden="true" />}
              </div>
              <div className="text-sm">
                <p className={s.done ? "font-semibold" : "text-neutral-500"}>{s.label}<span className="sr-only">{s.done ? " (complete)" : " (upcoming)"}</span></p>
                {s.at && <p className="text-xs text-neutral-500">{s.done ? fmt(s.at) : `Expected ${fmt(s.at)}`}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
