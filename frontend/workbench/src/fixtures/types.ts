// Shapes of the demo fixtures. Presenters edit fixtures.ts; the app only reads these types.

export interface Person {
  id: string;
  name: string;
  initials: string;
  title: string;
  kind?: "human" | "devin" | "bot";
}

export interface ExternalLink {
  label: string;
  url: string;
  kind: "session" | "pr" | "guide" | "board" | "other";
}

/** Cross-reference to another record inside the Workbench. */
export type RecordRef =
  | { kind: "issue"; key: string } // e.g. "OW-42"; project = prefix before the dash
  | { kind: "incident"; number: string }
  | { kind: "change"; number: string }
  | { kind: "problem"; number: string }
  | { kind: "service"; name: string }
  | { kind: "thread"; channel: string; messageId: string };

// ---------------------------------------------------------------- issue tracker

export type IssueStatus = "backlog" | "selected" | "in_progress" | "in_review" | "done";

export interface IssueComment {
  id: string;
  authorId: string;
  at: string; // ISO 8601, UTC
  body: string; // markdown-ish, see Markdown renderer
}

export interface ActivityEntry {
  at: string;
  actorId: string;
  text: string;
}

export interface Issue {
  key: string;
  projectKey: string;
  title: string;
  type: "Story" | "Bug" | "Task" | "Epic";
  priority: "Highest" | "High" | "Medium" | "Low";
  status: IssueStatus;
  assigneeId?: string;
  reporterId: string;
  labels: string[];
  createdAt: string;
  description: string;
  links: ExternalLink[];
  related: RecordRef[];
  comments: IssueComment[];
  activity: ActivityEntry[];
}

export interface Project {
  key: string;
  name: string;
  description: string;
  leadId: string;
}

// ------------------------------------------------------------------------ chat

export interface Reaction {
  name: string; // short name, e.g. "eyes", "white_check_mark"; see reactionGlyphs
  count: number;
}

export interface ChatReply {
  id: string;
  authorId: string;
  at: string;
  text: string;
  reactions: Reaction[];
}

export interface ChatMessage {
  id: string; // unique across the workspace, used in /chat/:channel/t/:messageId
  channelId: string;
  authorId: string;
  at: string;
  text: string;
  reactions: Reaction[];
  replies: ChatReply[];
}

export interface Channel {
  id: string; // "incidents", rendered as #incidents
  topic: string;
}

// ------------------------------------------------------------------------ ITSM

export interface WorkNote {
  at: string;
  authorId: string;
  text: string;
}

export type Priority = "1 - Critical" | "2 - High" | "3 - Moderate" | "4 - Low";

export interface ItsmRecordBase {
  number: string;
  shortDescription: string;
  description: string;
  priority: Priority;
  assignmentGroup: string;
  assignedToId?: string;
  serviceName: string; // links to /itsm/services/:name
  openedAt: string;
  workNotes: WorkNote[];
  related: RecordRef[];
  links: ExternalLink[];
}

export interface Incident extends ItsmRecordBase {
  state: "New" | "In Progress" | "On Hold" | "Resolved" | "Closed";
  resolvedAt?: string;
  resolutionNotes?: string;
}

export interface Problem extends ItsmRecordBase {
  state: "Assess" | "Root Cause Analysis" | "Fix in Progress" | "Resolved" | "Closed";
  rootCause: string;
  workaround: string;
}

export interface ChangeRequest extends ItsmRecordBase {
  // Nothing in the portfolio is merged, so a change is never "Implemented".
  state: "Awaiting approval" | "Scheduled";
  type: "Normal" | "Standard" | "Emergency";
  risk: "High" | "Moderate" | "Low";
  plannedStart: string;
  plannedEnd: string;
  implementationPlan: string;
  backoutPlan: string;
}

export type SupportStatus = "Supported" | "Partial" | "Unsupported" | "Licence risk" | "Not assessed";

export interface ServiceCi {
  name: string; // URL segment, e.g. "document-service"
  displayName: string;
  path: string; // repo path, e.g. "services/document-service"
  category: "service" | "frontend" | "client" | "etl";
  owner: string; // owning team / assignment group
  runtime: string;
  language: string;
  framework: string;
  supportStatus: SupportStatus;
  supportNote: string;
}

// ---------------------------------------------------------------------- bundle

export interface Fixtures {
  currentUserId: string; // author used by the chat composer and new comments
  people: Person[];
  projects: Project[];
  issues: Issue[];
  channels: Channel[];
  messages: ChatMessage[];
  incidents: Incident[];
  problems: Problem[];
  changes: ChangeRequest[];
  services: ServiceCi[];
}
