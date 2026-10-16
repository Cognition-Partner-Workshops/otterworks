import type { ActivityEntry, Fixtures, IssueComment, IssueStatus } from "@/fixtures/types";

export const BOARDS_STORAGE_KEY = "workbench.boards.v1";

export interface SavedIssue {
  status: IssueStatus;
  comments: IssueComment[];
  activity: ActivityEntry[];
}

export interface BoardState {
  issues: Record<string, SavedIssue>;
}

const statusNames: Record<IssueStatus, string> = {
  backlog: "Backlog",
  selected: "Selected",
  in_progress: "In progress",
  in_review: "In review",
  done: "Done",
};

function getStorage(storage?: Storage): Storage {
  return storage ?? window.localStorage;
}

export function loadBoardState(fixtures: Fixtures, storage?: Storage): BoardState {
  const base: BoardState = {
    issues: Object.fromEntries(fixtures.issues.map((issue) => [issue.key, {
      status: issue.status,
      comments: [...issue.comments],
      activity: [...issue.activity],
    }])),
  };
  try {
    const saved = getStorage(storage).getItem(BOARDS_STORAGE_KEY);
    if (!saved) return base;
    const parsed = JSON.parse(saved) as BoardState;
    for (const issue of fixtures.issues) {
      const override = parsed.issues?.[issue.key];
      if (override) {
        base.issues[issue.key] = {
          status: override.status ?? issue.status,
          comments: Array.isArray(override.comments) ? override.comments : [...issue.comments],
          activity: Array.isArray(override.activity) ? override.activity : [...issue.activity],
        };
      }
    }
  } catch {
    return base;
  }
  return base;
}

export function moveIssue(
  fixtures: Fixtures,
  issueKey: string,
  status: IssueStatus,
  storage?: Storage,
  at = new Date().toISOString(),
): BoardState {
  const state = loadBoardState(fixtures, storage);
  const issue = fixtures.issues.find((item) => item.key === issueKey);
  const current = state.issues[issueKey];
  if (!issue || !current || current.status === status) return state;
  state.issues[issueKey] = {
    ...current,
    status,
    activity: [...current.activity, {
      at,
      actorId: fixtures.currentUserId,
      text: `Moved from ${statusNames[current.status]} to ${statusNames[status]}`,
    }],
  };
  getStorage(storage).setItem(BOARDS_STORAGE_KEY, JSON.stringify(state));
  return state;
}

export function addIssueComment(
  fixtures: Fixtures,
  issueKey: string,
  body: string,
  storage?: Storage,
  at = new Date().toISOString(),
): BoardState {
  const state = loadBoardState(fixtures, storage);
  const issue = fixtures.issues.find((item) => item.key === issueKey);
  const current = state.issues[issueKey];
  if (!issue || !current || !body.trim()) return state;
  const comment: IssueComment = {
    id: `comment-${current.comments.length + 1}`,
    authorId: fixtures.currentUserId,
    at,
    body: body.trim(),
  };
  state.issues[issueKey] = {
    ...current,
    comments: [...current.comments, comment],
    activity: [...current.activity, {
      at,
      actorId: fixtures.currentUserId,
      text: "Added a comment",
    }],
  };
  getStorage(storage).setItem(BOARDS_STORAGE_KEY, JSON.stringify(state));
  return state;
}
