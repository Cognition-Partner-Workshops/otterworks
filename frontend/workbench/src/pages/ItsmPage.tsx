import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { fixtures } from "@/fixtures/fixtures";
import type { ChangeRequest, Incident, Problem, ServiceCi } from "@/fixtures/types";
import { MarkdownText } from "@/components/MarkdownText";
import { ExternalLinks, Panel, RelatedRecords, SupportBadge, formatUtc, personFor } from "@/components/shared";

type RecordSection = "incidents" | "problems" | "changes" | "services";
type WorkRecord = Incident | Problem | ChangeRequest;

const tabs: { id: RecordSection; label: string }[] = [
  { id: "incidents", label: "Incidents" },
  { id: "problems", label: "Problems" },
  { id: "changes", label: "Changes" },
  { id: "services", label: "Services" },
];

function NotFound({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-6xl px-5 py-8"><Panel title="Record not found">{children}<Link to="/itsm/incidents" className="mt-3 inline-block font-medium hover:underline">Back to ITSM</Link></Panel></div>;
}

function ItsmFrame({ children, section }: { children: ReactNode; section: RecordSection }) {
  return (
    <div className="mx-auto max-w-6xl px-5 py-8">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-600">ITSM</p>
        <h1 className="mt-2 text-3xl font-semibold text-otter-900">Service operations</h1>
      </div>
      <nav aria-label="ITSM sections" className="mb-5 flex flex-wrap gap-1 border-b border-otter-200">
        {tabs.map((tab) => (
          <Link key={tab.id} to={`/itsm/${tab.id}`} className={`border-b-2 px-4 py-3 text-sm font-medium ${section === tab.id ? "border-accent-500 text-otter-900" : "border-transparent text-slate-600 hover:text-otter-900"}`}>
            {tab.label}
          </Link>
        ))}
      </nav>
      {children}
    </div>
  );
}

function RecordTable({ rows, section }: { rows: WorkRecord[]; section: Exclude<RecordSection, "services"> }) {
  return (
    <div className="overflow-hidden rounded border border-otter-200 bg-white shadow-sm">
      <table className="w-full border-collapse text-left">
        <thead className="bg-otter-50 text-xs uppercase tracking-wide text-slate-600">
          <tr>
            <th className="px-4 py-3 font-semibold">Number</th>
            <th className="px-4 py-3 font-semibold">Short description</th>
            <th className="px-4 py-3 font-semibold">State</th>
            <th className="px-4 py-3 font-semibold">Priority</th>
            <th className="px-4 py-3 font-semibold">Assignment group</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-otter-100">
          {rows.map((record) => (
            <tr key={record.number} className="hover:bg-otter-50">
              <td className="whitespace-nowrap px-4 py-4 text-sm font-semibold"><Link className="hover:underline" to={`/itsm/${section}/${record.number}`}>{record.number}</Link></td>
              <td className="px-4 py-4 text-sm text-otter-900">{record.shortDescription}</td>
              <td className="whitespace-nowrap px-4 py-4 text-sm">{record.state}</td>
              <td className="whitespace-nowrap px-4 py-4 text-sm">{record.priority}</td>
              <td className="px-4 py-4 text-sm">{record.assignmentGroup}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <p className="p-5 text-sm text-slate-500">No records found.</p>}
    </div>
  );
}

function ServicesTable() {
  return (
    <div className="overflow-hidden rounded border border-otter-200 bg-white shadow-sm">
      <table className="w-full border-collapse text-left">
        <thead className="bg-otter-50 text-xs uppercase tracking-wide text-slate-600">
          <tr>
            <th className="px-4 py-3 font-semibold">Service</th>
            <th className="px-4 py-3 font-semibold">Owner</th>
            <th className="px-4 py-3 font-semibold">Runtime</th>
            <th className="px-4 py-3 font-semibold">Support status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-otter-100">
          {fixtures.services.map((service) => (
            <tr key={service.name} className="hover:bg-otter-50">
              <td className="px-4 py-4 text-sm font-semibold"><Link className="hover:underline" to={`/itsm/services/${service.name}`}>{service.displayName}</Link></td>
              <td className="px-4 py-4 text-sm">{service.owner}</td>
              <td className="px-4 py-4 text-sm">{service.runtime}</td>
              <td className="px-4 py-4"><SupportBadge status={service.supportStatus} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      {fixtures.services.length === 0 && <p className="p-5 text-sm text-slate-500">No services found.</p>}
    </div>
  );
}

export function ItsmListPage({ section }: { section: RecordSection }) {
  return (
    <ItsmFrame section={section}>
      <h2 className="mb-4 text-lg font-semibold text-otter-900">{tabs.find((tab) => tab.id === section)?.label}</h2>
      {section === "services" ? (
        <ServicesTable />
      ) : (
        <RecordTable
          section={section}
          rows={section === "incidents" ? fixtures.incidents : section === "problems" ? fixtures.problems : fixtures.changes}
        />
      )}
    </ItsmFrame>
  );
}

function RecordFields({ record }: { record: WorkRecord }) {
  if ("rootCause" in record) {
    return (
      <section className="grid gap-4 sm:grid-cols-2">
        <div className="rounded bg-otter-50 p-4"><h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Root cause</h2><div className="text-sm leading-6"><MarkdownText text={record.rootCause} /></div></div>
        <div className="rounded bg-otter-50 p-4"><h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Workaround</h2><div className="text-sm leading-6"><MarkdownText text={record.workaround} /></div></div>
      </section>
    );
  }
  if ("implementationPlan" in record) {
    return (
      <section className="grid gap-4 sm:grid-cols-2">
        <div className="rounded bg-otter-50 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Change plan</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div><dt className="text-slate-500">Type</dt><dd className="font-medium">{record.type}</dd></div>
            <div><dt className="text-slate-500">Risk</dt><dd className="font-medium">{record.risk}</dd></div>
            <div><dt className="text-slate-500">Planned window</dt><dd className="font-medium">{formatUtc(record.plannedStart)} to {formatUtc(record.plannedEnd)}</dd></div>
          </dl>
          <h3 className="mb-2 mt-4 text-sm font-semibold text-otter-900">Implementation plan</h3>
          <div className="text-sm leading-6"><MarkdownText text={record.implementationPlan} /></div>
          <h3 className="mb-2 mt-4 text-sm font-semibold text-otter-900">Backout plan</h3>
          <div className="text-sm leading-6"><MarkdownText text={record.backoutPlan} /></div>
        </div>
      </section>
    );
  }
  if (record.resolutionNotes) {
    return <section className="rounded bg-emerald-50 p-4"><h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-emerald-800">Resolution</h2><div className="text-sm leading-6"><MarkdownText text={record.resolutionNotes} /></div></section>;
  }
  return null;
}

export function ItsmRecordPage({ section, number }: { section: Exclude<RecordSection, "services">; number: string }) {
  const record: WorkRecord | undefined = section === "incidents"
    ? fixtures.incidents.find((item) => item.number === number)
    : section === "problems"
      ? fixtures.problems.find((item) => item.number === number)
      : fixtures.changes.find((item) => item.number === number);
  if (!record) return <NotFound><p>No {section.slice(0, -1)} record matches {number}.</p></NotFound>;
  const assignedTo = personFor(fixtures.people, record.assignedToId);
  return (
    <ItsmFrame section={section}>
      <div className="mb-5 flex flex-wrap items-center gap-2 text-sm text-slate-500">
        <Link to={`/itsm/${section}`} className="hover:underline">{tabs.find((tab) => tab.id === section)?.label}</Link><span>/</span><span>{record.number}</span>
      </div>
      <article className="rounded border border-otter-200 bg-white p-6 shadow-sm">
        <header className="border-b border-otter-100 pb-5">
          <p className="text-sm font-semibold text-otter-600">{record.number} · {record.state}</p>
          <h2 className="mt-2 text-2xl font-semibold text-otter-900">{record.shortDescription}</h2>
          <p className="mt-2 text-sm text-slate-600">Opened {formatUtc(record.openedAt)}</p>
        </header>
        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div className="space-y-6">
            <section><h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Description</h3><div className="leading-7 text-slate-700"><MarkdownText text={record.description} /></div></section>
            <RecordFields record={record} />
            <section><h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Links</h3><ExternalLinks links={record.links} /></section>
            <section><h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Related records</h3><RelatedRecords records={record.related} /></section>
            <section>
              <h3 className="mb-3 text-lg font-semibold text-otter-900">Work notes</h3>
              <ol className="space-y-4">
                {[...record.workNotes].sort((a, b) => b.at.localeCompare(a.at)).map((note, index) => {
                  const author = personFor(fixtures.people, note.authorId);
                  return (
                    <li key={`${note.at}-${index}`} className="flex gap-3 border-b border-otter-100 pb-4">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-otter-100 text-xs font-semibold text-otter-700">{author.initials}</span>
                      <div><div className="flex flex-wrap items-baseline gap-2"><span className="font-medium text-otter-900">{author.name}</span><time className="text-xs text-slate-500">{formatUtc(note.at)}</time></div><div className="mt-2 text-sm leading-6 text-slate-700"><MarkdownText text={note.text} /></div></div>
                    </li>
                  );
                })}
              </ol>
            </section>
          </div>
          <aside className="space-y-4 rounded bg-otter-50 p-4">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Record details</h3>
            <dl className="space-y-3 text-sm">
              <div><dt className="text-slate-500">State</dt><dd className="mt-1 font-medium">{record.state}</dd></div>
              <div><dt className="text-slate-500">Priority</dt><dd className="mt-1 font-medium">{record.priority}</dd></div>
              <div><dt className="text-slate-500">Assignment group</dt><dd className="mt-1 font-medium">{record.assignmentGroup}</dd></div>
              <div><dt className="text-slate-500">Assigned to</dt><dd className="mt-1 font-medium">{assignedTo.name}</dd></div>
              <div><dt className="text-slate-500">Service</dt><dd className="mt-1 font-medium"><Link to={`/itsm/services/${record.serviceName}`} className="hover:underline">{record.serviceName}</Link></dd></div>
            </dl>
          </aside>
        </div>
      </article>
    </ItsmFrame>
  );
}

export function ItsmServicePage({ name }: { name: string }) {
  const service: ServiceCi | undefined = fixtures.services.find((item) => item.name === name);
  if (!service) return <NotFound><p>No service matches {name}.</p></NotFound>;
  const relatedIncidents = fixtures.incidents.filter((item) => item.serviceName === service.name);
  const relatedProblems = fixtures.problems.filter((item) => item.serviceName === service.name);
  const relatedChanges = fixtures.changes.filter((item) => item.serviceName === service.name);
  return (
    <ItsmFrame section="services">
      <div className="mb-5"><Link to="/itsm/services" className="text-sm text-slate-500 hover:underline">Services</Link><span className="mx-2 text-sm text-slate-400">/</span><span className="text-sm text-slate-500">{service.name}</span></div>
      <article className="rounded border border-otter-200 bg-white p-6 shadow-sm">
        <header className="flex flex-wrap items-start justify-between gap-4 border-b border-otter-100 pb-5">
          <div><p className="text-sm font-semibold text-otter-600">{service.category}</p><h2 className="mt-2 text-2xl font-semibold text-otter-900">{service.displayName}</h2></div>
          <SupportBadge status={service.supportStatus} />
        </header>
        <dl className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {([
            ["Name", service.name],
            ["Repository path", service.path],
            ["Category", service.category],
            ["Owner", service.owner],
            ["Runtime", service.runtime],
            ["Language", service.language],
            ["Framework", service.framework],
            ["Support status", service.supportStatus],
            ["Support note", service.supportNote],
          ] as [string, string][]).map(([label, value]) => (
            <div key={label} className="rounded bg-otter-50 p-3"><dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-1 text-sm text-otter-900">{value}</dd></div>
          ))}
        </dl>
        <section className="mt-7 space-y-5">
          <h3 className="text-lg font-semibold text-otter-900">Related records</h3>
          <RecordGroup title="Incidents" records={relatedIncidents.map((record) => ({ number: record.number, description: record.shortDescription, route: `/itsm/incidents/${record.number}` }))} />
          <RecordGroup title="Problems" records={relatedProblems.map((record) => ({ number: record.number, description: record.shortDescription, route: `/itsm/problems/${record.number}` }))} />
          <RecordGroup title="Changes" records={relatedChanges.map((record) => ({ number: record.number, description: record.shortDescription, route: `/itsm/changes/${record.number}` }))} />
        </section>
      </article>
    </ItsmFrame>
  );
}

function RecordGroup({ title, records }: { title: string; records: { number: string; description: string; route: string }[] }) {
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold text-slate-600">{title}</h4>
      {records.length ? (
        <ul className="space-y-2">
          {records.map((record) => <li key={record.number} className="rounded border border-otter-100 p-3 text-sm"><Link className="font-semibold hover:underline" to={record.route}>{record.number}</Link><span className="ml-2 text-slate-600">{record.description}</span></li>)}
        </ul>
      ) : <p className="text-sm text-slate-500">No related {title.toLowerCase()}.</p>}
    </div>
  );
}
