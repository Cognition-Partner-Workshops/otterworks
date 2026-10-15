import { useState } from "react";
import { Link } from "react-router-dom";
import type { DragEvent, FormEvent } from "react";
import { fixtures } from "@/fixtures/fixtures";
import type { Issue, IssueStatus } from "@/fixtures/types";
import { Avatar, ExternalLinks, Panel, RelatedRecords, ResetDemoButton, formatUtc, personFor } from "@/components/shared";
import { MarkdownText } from "@/components/MarkdownText";
import { addIssueComment, loadBoardState, moveIssue } from "@/stores/boardsStore";

const statuses: IssueStatus[] = ["backlog", "selected", "in_progress", "in_review", "done"];
const statusLabels: Record<IssueStatus, string> = {
  backlog: "Backlog",
  selected: "Selected",
  in_progress: "In progress",
  in_review: "In review",
  done: "Done",
};

function NotFound({ message }: { message: string }) {
  return (
    <Panel title="Not found">
      <p>{message}</p>
      <Link className="mt-3 inline-block font-medium hover:underline" to="/boards">Back to projects</Link>
    </Panel>
  );
}

export function ProjectsPage() {
  const projects = fixtures.projects;
  const state = loadBoardState(fixtures);
  return (
    <div className="mx-auto max-w-6xl px-5 py-8">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-600">Issue tracker</p>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><h1 className="mt-2 text-3xl font-semibold text-otter-900">Projects</h1><p className="mt-2 text-slate-600">Browse active work across the demo portfolio.</p></div>
          <ResetDemoButton />
        </div>
      </div>
      <div className="overflow-hidden rounded border border-otter-200 bg-white shadow-sm">
        <table className="w-full border-collapse text-left">
          <thead className="bg-otter-50 text-xs uppercase tracking-wide text-slate-600">
            <tr>
              <th className="px-5 py-3 font-semibold">Key</th>
              <th className="px-5 py-3 font-semibold">Name</th>
              <th className="px-5 py-3 font-semibold">Lead</th>
              <th className="px-5 py-3 font-semibold">Issues</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-otter-100">
            {projects.map((project) => {
              const lead = personFor(fixtures.people, project.leadId);
              const issueCount = fixtures.issues.filter((issue) => issue.projectKey === project.key).length;
              return (
                <tr key={project.key} className="hover:bg-otter-50">
                  <td className="px-5 py-4"><Link className="font-semibold hover:underline" to={`/boards/${project.key}`}>{project.key}</Link></td>
                  <td className="px-5 py-4">
                    <Link className="font-medium text-otter-900 hover:underline" to={`/boards/${project.key}`}>{project.name}</Link>
                    <p className="mt-1 text-sm text-slate-500">{project.description}</p>
                  </td>
                  <td className="px-5 py-4 text-sm">{lead.name}</td>
                  <td className="px-5 py-4 text-sm">{issueCount}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function IssueCard({ issue, onDragStart }: { issue: Issue; onDragStart: (event: DragEvent<HTMLElement>, key: string) => void }) {
  const assignee = personFor(fixtures.people, issue.assigneeId);
  return (
    <article
      draggable
      onDragStart={(event) => onDragStart(event, issue.key)}
      className="rounded border border-otter-200 bg-white p-3 shadow-sm transition hover:border-otter-400 hover:shadow"
    >
      <div className="flex items-start justify-between gap-2">
        <Link className="text-xs font-semibold text-otter-600 hover:underline" to={`/boards/${issue.projectKey}/${issue.key}`}>{issue.key}</Link>
        <span className="rounded bg-otter-50 px-2 py-0.5 text-[11px] font-medium text-slate-600">{issue.type}</span>
      </div>
      <Link className="mt-2 block text-sm font-medium leading-5 text-otter-900 hover:underline" to={`/boards/${issue.projectKey}/${issue.key}`}>
        {issue.title}
      </Link>
      <div className="mt-3 flex flex-wrap gap-1">
        {issue.labels.map((label) => <span key={label} className="rounded bg-otter-100 px-2 py-0.5 text-[11px] text-otter-700">{label}</span>)}
        <span className="rounded bg-amber-50 px-2 py-0.5 text-[11px] text-amber-800">{issue.priority}</span>
      </div>
      <div className="mt-3 flex items-center justify-between border-t border-otter-100 pt-2">
        <span className="text-xs text-slate-500">{assignee.name}</span>
        <Avatar person={assignee} size="small" />
      </div>
    </article>
  );
}

export function ProjectBoard({ projectKey }: { projectKey: string }) {
  const project = fixtures.projects.find((item) => item.key === projectKey);
  const [revision, setRevision] = useState(0);
  if (!project) return <NotFound message={`Project ${projectKey} was not found.`} />;
  const state = loadBoardState(fixtures);
  const issues = fixtures.issues.filter((issue) => issue.projectKey === project.key).map((issue) => ({
    ...issue,
    status: state.issues[issue.key]?.status ?? issue.status,
  }));

  const handleDragStart = (event: DragEvent<HTMLElement>, issueKey: string) => {
    event.dataTransfer.setData("text/plain", issueKey);
    event.dataTransfer.effectAllowed = "move";
  };
  const handleDrop = (event: DragEvent<HTMLElement>, status: IssueStatus) => {
    event.preventDefault();
    const issueKey = event.dataTransfer.getData("text/plain");
    if (issueKey) {
      moveIssue(fixtures, issueKey, status);
      setRevision((value) => value + 1);
    }
  };
  const handleDragOver = (event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  };

  void revision;
  return (
    <div className="mx-auto max-w-[1600px] px-5 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-600">Issue tracker / {project.key}</p>
          <h1 className="mt-2 text-3xl font-semibold text-otter-900">{project.name}</h1>
          <p className="mt-2 text-slate-600">{project.description}</p>
        </div>
        <div className="flex items-center gap-3"><Link className="text-sm font-medium hover:underline" to="/boards">All projects</Link><ResetDemoButton /></div>
      </div>
      <div className="overflow-x-auto pb-4">
        <div className="grid min-w-[920px] grid-cols-5 gap-3">
          {statuses.map((status) => {
            const columnIssues = issues.filter((issue) => issue.status === status);
            return (
              <section
                key={status}
                className="min-h-[16rem] rounded border border-otter-200 bg-otter-50/70 p-3"
                onDrop={(event) => handleDrop(event, status)}
                onDragOver={handleDragOver}
                aria-label={`${statusLabels[status]} column`}
              >
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-otter-900">{statusLabels[status]}</h2>
                  <span className="rounded bg-white px-2 py-0.5 text-xs text-slate-600">{columnIssues.length}</span>
                </div>
                <div className="space-y-2">
                  {columnIssues.map((issue) => <IssueCard key={issue.key} issue={issue} onDragStart={handleDragStart} />)}
                </div>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function IssueDetail({ projectKey, issueKey }: { projectKey: string; issueKey: string }) {
  const [revision, setRevision] = useState(0);
  const [comment, setComment] = useState("");
  const project = fixtures.projects.find((item) => item.key === projectKey);
  const fixtureIssue = fixtures.issues.find((item) => item.key === issueKey && item.projectKey === projectKey);
  if (!project || !fixtureIssue) return <NotFound message="The project or issue was not found." />;

  const state = loadBoardState(fixtures);
  const saved = state.issues[fixtureIssue.key];
  const issue = { ...fixtureIssue, ...saved };
  const reporter = personFor(fixtures.people, issue.reporterId);
  const assignee = personFor(fixtures.people, issue.assigneeId);
  const handleStatusChange = (status: IssueStatus) => {
    moveIssue(fixtures, issue.key, status);
    setRevision((value) => value + 1);
  };
  const handleComment = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!comment.trim()) return;
    addIssueComment(fixtures, issue.key, comment);
    setComment("");
    setRevision((value) => value + 1);
  };

  void revision;
  return (
    <div className="mx-auto max-w-6xl px-5 py-8">
      <div className="mb-5 flex items-center justify-between gap-2 text-sm text-slate-500">
        <div className="flex items-center gap-2">
        <Link to="/boards" className="hover:underline">Projects</Link><span>/</span>
        <Link to={`/boards/${project.key}`} className="hover:underline">{project.key}</Link><span>/</span><span>{issue.key}</span>
        </div>
        <ResetDemoButton />
      </div>
      <div className="rounded border border-otter-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-otter-600">{issue.key} · {issue.type}</p>
            <h1 className="mt-2 text-2xl font-semibold text-otter-900">{issue.title}</h1>
          </div>
          <label className="flex items-center gap-2 text-sm font-medium text-slate-600">
            Move to
            <select
              aria-label="Move to"
              className="rounded border border-otter-300 bg-white px-3 py-2 text-otter-900"
              value={issue.status}
              onChange={(event) => handleStatusChange(event.target.value as IssueStatus)}
            >
              {statuses.map((status) => <option key={status} value={status}>{statusLabels[status]}</option>)}
            </select>
          </label>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div className="space-y-6">
            <section>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Description</h2>
              <div className="leading-7 text-slate-700"><MarkdownText text={issue.description} /></div>
            </section>
            <section>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Links</h2>
              <ExternalLinks links={issue.links} />
            </section>
            <section>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Related records</h2>
              <RelatedRecords records={issue.related} />
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold text-otter-900">Comments</h2>
              <div className="space-y-4">
                {issue.comments.map((item) => {
                  const author = personFor(fixtures.people, item.authorId);
                  return (
                    <article key={item.id} className="flex gap-3 border-b border-otter-100 pb-4">
                      <Avatar person={author} size="small" />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-baseline gap-x-2">
                          <span className="font-medium text-otter-900">{author.name}</span>
                          <time className="text-xs text-slate-500">{formatUtc(item.at)}</time>
                        </div>
                        <div className="mt-2 text-sm leading-6 text-slate-700"><MarkdownText text={item.body} /></div>
                      </div>
                    </article>
                  );
                })}
              </div>
              <form className="mt-5 space-y-3" onSubmit={handleComment}>
                <label className="block text-sm font-medium text-otter-900" htmlFor="comment">Add a comment</label>
                <textarea id="comment" className="min-h-24 w-full rounded border border-otter-300 p-3 focus:border-otter-500 focus:outline-none" value={comment} onChange={(event) => setComment(event.target.value)} />
                <button className="rounded bg-otter-600 px-4 py-2 text-sm font-semibold text-white hover:bg-otter-700" type="submit">Add comment</button>
              </form>
            </section>
          </div>
          <aside className="space-y-4 rounded bg-otter-50 p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Details</h2>
            <dl className="space-y-3 text-sm">
              <div><dt className="text-slate-500">Status</dt><dd className="mt-1 font-medium">{statusLabels[issue.status]}</dd></div>
              <div><dt className="text-slate-500">Type</dt><dd className="mt-1 font-medium">{issue.type}</dd></div>
              <div><dt className="text-slate-500">Priority</dt><dd className="mt-1 font-medium">{issue.priority}</dd></div>
              <div><dt className="text-slate-500">Assignee</dt><dd className="mt-1 flex items-center gap-2"><Avatar person={assignee} size="small" />{assignee.name}</dd></div>
              <div><dt className="text-slate-500">Reporter</dt><dd className="mt-1 font-medium">{reporter.name}</dd></div>
              <div><dt className="text-slate-500">Labels</dt><dd className="mt-1 flex flex-wrap gap-1">{issue.labels.map((label) => <span key={label} className="rounded bg-white px-2 py-1 text-xs">{label}</span>)}</dd></div>
            </dl>
            <div className="border-t border-otter-200 pt-4">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Activity log</h2>
              <ol className="space-y-3">
                {issue.activity.map((entry, index) => (
                  <li key={`${entry.at}-${index}`} className="text-sm">
                    <p className="text-slate-700">{entry.text}</p>
                    <time className="text-xs text-slate-500">{formatUtc(entry.at)}</time>
                  </li>
                ))}
              </ol>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
