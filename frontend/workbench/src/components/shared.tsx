import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import type { ExternalLink, Person, RecordRef, SupportStatus } from "@/fixtures/types";
import { resetWorkbenchData } from "@/stores/resetStore";

const supportStyles: Record<SupportStatus, string> = {
  Supported: "bg-emerald-100 text-emerald-800",
  Partial: "bg-amber-100 text-amber-800",
  Unsupported: "bg-rose-100 text-rose-800",
  "Licence risk": "bg-orange-100 text-orange-800",
  "Not assessed": "bg-slate-100 text-slate-700",
};

export function formatUtc(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const formatted = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: "UTC",
  }).format(date);
  return `${formatted} UTC`;
}

export function personFor(people: Person[], id?: string): Person {
  return people.find((person) => person.id === id) ?? {
    id: id ?? "unknown",
    name: "Unassigned",
    initials: "?",
    title: "",
  };
}

export function Avatar({ person, size = "normal" }: { person: Person; size?: "normal" | "small" }) {
  const colors = ["bg-otter-600", "bg-teal-700", "bg-violet-700", "bg-amber-700", "bg-rose-700"];
  const colorIndex = [...person.id].reduce((sum, char) => sum + char.charCodeAt(0), 0) % colors.length;
  const dimension = size === "small" ? "h-7 w-7 text-[10px]" : "h-9 w-9 text-xs";
  return (
    <span className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white ${colors[colorIndex]} ${dimension}`} title={person.name} aria-label={person.name}>
      {person.initials}
    </span>
  );
}

export function ExternalLinks({ links }: { links: ExternalLink[] }) {
  if (!links.length) return <p className="text-sm text-slate-500">No links</p>;
  return (
    <ul className="space-y-2">
      {links.map((link) => (
        <li key={`${link.url}-${link.label}`}>
          <a href={link.url} target="_blank" rel="noreferrer" className="text-sm font-medium hover:underline">
            {link.label}
          </a>
          <span className="ml-2 text-xs uppercase tracking-wide text-slate-500">{link.kind}</span>
        </li>
      ))}
    </ul>
  );
}

export function recordHref(ref: RecordRef): string {
  switch (ref.kind) {
    case "issue":
      return `/boards/${ref.key.split("-")[0]}/${ref.key}`;
    case "incident":
      return `/itsm/incidents/${ref.number}`;
    case "problem":
      return `/itsm/problems/${ref.number}`;
    case "change":
      return `/itsm/changes/${ref.number}`;
    case "service":
      return `/itsm/services/${ref.name}`;
    case "thread":
      return `/chat/${ref.channel}/t/${ref.messageId}`;
  }
}

export function recordLabel(ref: RecordRef): string {
  switch (ref.kind) {
    case "issue":
      return ref.key;
    case "incident":
    case "problem":
    case "change":
      return ref.number;
    case "service":
      return ref.name;
    case "thread":
      return `#${ref.channel} thread`;
  }
}

export function RelatedRecords({ records }: { records: RecordRef[] }) {
  if (!records.length) return <p className="text-sm text-slate-500">No related records</p>;
  return (
    <ul className="flex flex-wrap gap-2">
      {records.map((record) => (
        <li key={`${record.kind}-${recordLabel(record)}`}>
          <Link className="rounded border border-otter-200 bg-white px-2 py-1 text-sm font-medium hover:bg-otter-50" to={recordHref(record)}>
            {recordLabel(record)}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function SupportBadge({ status }: { status: SupportStatus }) {
  return <span className={`inline-flex rounded px-2 py-1 text-xs font-semibold ${supportStyles[status]}`}>{status}</span>;
}

export function ResetDemoButton({ className = "" }: { className?: string }) {
  return (
    <button
      type="button"
      className={`rounded border border-otter-300 bg-white px-3 py-2 text-sm font-medium text-otter-800 hover:bg-otter-50 ${className}`}
      onClick={() => {
        resetWorkbenchData();
        window.location.reload();
      }}
    >
      Reset demo data
    </button>
  );
}

export function Panel({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <section className="rounded border border-otter-200 bg-white p-6 shadow-sm">
      <h1 className="text-xl font-semibold text-otter-900">{title}</h1>
      {children && <div className="mt-3 text-slate-600">{children}</div>}
    </section>
  );
}
