import { type ReactNode } from "react";

const OUTCOME_STYLE: Record<string, string> = {
  FAST_TRACK: "bg-otter-100 text-otter-800 border-otter-300",
  STANDARD: "bg-gray-100 text-gray-800 border-gray-300",
  LARGE_LOSS: "bg-accent-400/20 text-accent-600 border-accent-400",
  FRAUD_REVIEW: "bg-accent-500 text-white border-accent-600",
  DECLINE_NOT_IN_FORCE: "bg-red-50 text-red-800 border-red-300",
};

export function Outcome({ value }: { value: string | null }) {
  if (!value) return <span className="text-gray-500">none</span>;
  return (
    <span data-testid="outcome" className={`inline-block border px-2 py-0.5 text-sm font-semibold tracking-wide ${OUTCOME_STYLE[value] ?? "bg-gray-100 border-gray-300"}`}>
      {value}
    </span>
  );
}

export function Panel({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="bg-white border border-gray-300 rounded">
      <header className="flex items-center justify-between border-b border-gray-200 px-4 py-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-otter-800">{title}</h2>
        {aside}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="py-1.5 grid grid-cols-[11rem_1fr] gap-3 text-sm">
      <dt className="text-gray-500">{label}</dt>
      <dd className="text-gray-900">{children ?? <span className="text-gray-400">—</span>}</dd>
    </div>
  );
}

export function Evidence({ items }: { items: string[] }) {
  return <p className="mt-3 text-xs text-gray-500">Read from: {items.join(" · ")}</p>;
}

export function ErrorNote({ error }: { error: string | null }) {
  return error ? <p role="alert" className="mt-3 border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null;
}

export function LookupForm({ label, value, onChange, onSubmit, placeholder }: { label: string; value: string; onChange: (v: string) => void; onSubmit: () => void; placeholder: string }) {
  return (
    <form className="flex items-end gap-2 mb-4" onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
      <label className="flex flex-col text-xs text-gray-600">
        {label}
        <input value={value} onChange={(e) => onChange(e.target.value.trim().toUpperCase())} placeholder={placeholder}
          className="mt-1 w-64 border border-gray-300 rounded px-2 py-1.5 text-sm font-mono focus:outline-none focus:border-otter-600" />
      </label>
      <button className="bg-otter-600 hover:bg-otter-700 text-white text-sm px-3 py-1.5 rounded">Look up</button>
    </form>
  );
}
