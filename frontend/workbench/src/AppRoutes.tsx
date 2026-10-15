import { Link, NavLink, Navigate, Route, Routes, useParams } from "react-router-dom";
import { fixtures } from "@/fixtures/fixtures";
import { Panel, ResetDemoButton } from "@/components/shared";
import { ChannelPage, ThreadPage } from "@/pages/ChatPage";
import { IssueDetail, ProjectBoard, ProjectsPage } from "@/pages/BoardsPage";
import { ItsmListPage, ItsmRecordPage, ItsmServicePage } from "@/pages/ItsmPage";

function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-otter-200 bg-white/95 shadow-sm backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-3">
        <Link to="/" className="text-lg font-bold tracking-tight text-otter-900">OtterWorks Workbench</Link>
        <nav aria-label="Main navigation" className="flex items-center gap-1">
          {[
            ["Issue tracker", "/boards"],
            ["Chat", "/chat"],
            ["ITSM", "/itsm"],
          ].map(([label, path]) => (
            <NavLink key={path} to={path} className={({ isActive }) => `rounded px-3 py-2 text-sm font-medium ${isActive ? "bg-otter-100 text-otter-900" : "text-slate-600 hover:bg-otter-50 hover:text-otter-900"}`}>
              {label}
            </NavLink>
          ))}
        </nav>
        <ResetDemoButton />
      </div>
    </header>
  );
}

function HomePage() {
  const owIssue = fixtures.issues.find((issue) => issue.key === "OW-42");
  const secIssue = fixtures.issues.find((issue) => issue.key === "SEC-12");
  const modIssue = fixtures.issues.find((issue) => issue.key === "MOD-11");
  const thread = fixtures.messages.find((message) => message.id === "p1001");
  const incident = fixtures.incidents.find((record) => record.number === "INC0010042");
  const problem = fixtures.problems.find((record) => record.number === "PRB0040008");
  const change = fixtures.changes.find((record) => record.number === "CHG0030017");
  const service = fixtures.services.find((record) => record.name === "document-service");

  const cards = [
    {
      title: "Issue tracker",
      description: "Follow projects, plan work, and review issue history.",
      links: [
        { label: owIssue?.key ?? "OW project", to: owIssue ? `/boards/${owIssue.projectKey}/${owIssue.key}` : "/boards" },
        { label: secIssue?.key ?? "SEC project", to: secIssue ? `/boards/${secIssue.projectKey}/${secIssue.key}` : "/boards" },
        { label: modIssue?.key ?? "MOD project", to: modIssue ? `/boards/${modIssue.projectKey}/${modIssue.key}` : "/boards" },
        { label: "Projects", to: "/boards" },
      ],
    },
    {
      title: "Chat",
      description: "Read the channel timeline and follow a discussion thread.",
      links: [
        { label: "#incidents", to: "/chat/incidents" },
        { label: thread ? "#incidents thread" : "Incident thread", to: thread ? `/chat/incidents/t/${thread.id}` : "/chat/incidents" },
        { label: "#security", to: "/chat/security" },
        { label: "#general", to: "/chat/general" },
      ],
    },
    {
      title: "ITSM",
      description: "Review service records, changes, and the service portfolio.",
      links: [
        { label: incident?.number ?? "Incidents", to: incident ? `/itsm/incidents/${incident.number}` : "/itsm/incidents" },
        { label: problem?.number ?? "Problems", to: problem ? `/itsm/problems/${problem.number}` : "/itsm/problems" },
        { label: change?.number ?? "Changes", to: change ? `/itsm/changes/${change.number}` : "/itsm/changes" },
        { label: service?.name ?? "Services", to: service ? `/itsm/services/${service.name}` : "/itsm/services" },
      ],
    },
  ];

  return (
    <main className="mx-auto max-w-7xl px-5 py-12">
      <div className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-600">Demo workspace</p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight text-otter-900">OtterWorks Workbench</h1>
        <p className="mt-4 text-lg leading-7 text-slate-600">A local, linked workspace for issue tracking, team chat, and IT service operations.</p>
      </div>
      <div className="mt-9 grid gap-5 lg:grid-cols-3">
        {cards.map((card) => (
          <article key={card.title} className="rounded border border-otter-200 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-otter-900">{card.title}</h2>
            <p className="mt-2 min-h-12 text-sm leading-6 text-slate-600">{card.description}</p>
            <ul className="mt-5 space-y-2 border-t border-otter-100 pt-4">
              {card.links.map((item) => (
                <li key={`${item.label}-${item.to}`}>
                  <Link to={item.to} className="inline-flex items-center gap-2 text-sm font-medium text-otter-700 hover:text-otter-900 hover:underline">
                    <span aria-hidden="true">›</span>{item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </main>
  );
}

function ProjectRoute() {
  const { project } = useParams();
  return project ? <ProjectBoard projectKey={project} /> : null;
}

function IssueRoute() {
  const { project, key } = useParams();
  return project && key ? <IssueDetail projectKey={project} issueKey={key} /> : null;
}

function ChannelRoute() {
  const { channel } = useParams();
  return channel ? <ChannelPage channelId={channel} /> : null;
}

function ThreadRoute() {
  const { channel, messageId } = useParams();
  return channel && messageId ? <ThreadPage channelId={channel} messageId={messageId} /> : null;
}

function ItsmRecordRoute({ section }: { section: "incidents" | "problems" | "changes" }) {
  const { number } = useParams();
  return number ? <ItsmRecordPage section={section} number={number} /> : null;
}

function ItsmServiceRoute() {
  const { name } = useParams();
  return name ? <ItsmServicePage name={name} /> : null;
}

function NotFoundPage() {
  return (
    <main className="mx-auto max-w-4xl px-5 py-12">
      <Panel title="Page not found">
        <p>This page is not part of the Workbench demo.</p>
        <Link to="/" className="mt-4 inline-block font-medium hover:underline">Return home</Link>
      </Panel>
    </main>
  );
}

export function AppRoutes() {
  return (
    <>
      <Header />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/boards" element={<ProjectsPage />} />
        <Route path="/boards/:project" element={<ProjectRoute />} />
        <Route path="/boards/:project/:key" element={<IssueRoute />} />
        <Route path="/chat" element={<Navigate to="/chat/incidents" replace />} />
        <Route path="/chat/:channel" element={<ChannelRoute />} />
        <Route path="/chat/:channel/t/:messageId" element={<ThreadRoute />} />
        <Route path="/itsm" element={<Navigate to="/itsm/incidents" replace />} />
        <Route path="/itsm/incidents" element={<ItsmListPage section="incidents" />} />
        <Route path="/itsm/problems" element={<ItsmListPage section="problems" />} />
        <Route path="/itsm/changes" element={<ItsmListPage section="changes" />} />
        <Route path="/itsm/services" element={<ItsmListPage section="services" />} />
        <Route path="/itsm/incidents/:number" element={<ItsmRecordRoute section="incidents" />} />
        <Route path="/itsm/problems/:number" element={<ItsmRecordRoute section="problems" />} />
        <Route path="/itsm/changes/:number" element={<ItsmRecordRoute section="changes" />} />
        <Route path="/itsm/services/:name" element={<ItsmServiceRoute />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </>
  );
}
