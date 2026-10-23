import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ResetDemoButton } from "@/components/shared";
import { IssueDetail } from "@/pages/BoardsPage";
import { ChannelPage } from "@/pages/ChatPage";
import { fixtures as baseFixtures } from "@/fixtures/fixtures";
import type { Fixtures } from "@/fixtures/types";
import { startWorkbench } from "@/main";
import { WorkbenchProvider } from "@/WorkbenchContext";
import { isValidTenantId, tenantUrl } from "@/tenant";
import { RemoteStorage, setWorkbenchStorage } from "@/stores/workbenchStorage";
import { addIssueComment, loadBoardState, moveIssue } from "@/stores/boardsStore";
import { sendChatMessage } from "@/stores/chatStore";

interface HostedState {
  boards: unknown | null;
  chat: unknown | null;
  settings: Record<string, unknown> | null;
}

const hostedUser = { sub: "alice", name: "Alice Attendee", email: "alice@example.com" };

const fixturesWithTenantLink: Fixtures = {
  ...baseFixtures,
  issues: baseFixtures.issues.map((issue) => issue.key === "OW-42" ? {
    ...issue,
    links: [...issue.links, {
      label: "Tenant service",
      url: "https://t-old.otterworks.app/api",
      kind: "other",
    }],
  } : issue),
};

function stubHostedApi(getState: () => HostedState) {
  const fetchMock = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
    if (url === "/api/me") {
      return Promise.resolve({ ok: true, status: 200, json: async () => hostedUser });
    }
    if (url === "/api/state") {
      return Promise.resolve({ ok: true, status: 200, json: async () => getState() });
    }
    if (url === "/api/state/settings" && options?.method === "PUT") {
      return Promise.resolve({ ok: true, status: 204 });
    }
    return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function bootWorkbench(mode: "hosted" | "static", path: string, fixtures: Fixtures = baseFixtures) {
  document.body.innerHTML = '<div id="root"></div>';
  window.history.replaceState({}, "", path);
  vi.stubEnv("VITE_WORKBENCH_MODE", mode);
  await startWorkbench(fixtures);
}

beforeEach(() => {
  localStorage.clear();
  setWorkbenchStorage(localStorage);
});

afterEach(() => {
  document.getElementById("root")?.remove();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("hosted workbench client", () => {
  it("validates tenant ids and rewrites only tenant service hosts", () => {
    expect(isValidTenantId("team-42")).toBe(true);
    expect(isValidTenantId("Team-42")).toBe(false);
    expect(isValidTenantId("-team")).toBe(false);
    expect(tenantUrl("https://t-old.otterworks.app/path?q=1", "team-42"))
      .toBe("https://t-team-42.demo.otterworks.app/path?q=1");
    expect(tenantUrl("https://api-t-old.demo.otterworks.app/v1?x=2", "team-42"))
      .toBe("https://api-t-team-42.demo.otterworks.app/v1?x=2");
    expect(tenantUrl("https://example.com/path", "team-42")).toBe("https://example.com/path");
    expect(tenantUrl("https://t-old.otterworks.app/path", "")).toBe("https://t-old.otterworks.app/path");
  });

  it("persists hosted tenant settings and restores tenant links on the next boot", async () => {
    let state: HostedState = { boards: null, chat: null, settings: null };
    const fetchMock = stubHostedApi(() => state);

    await bootWorkbench("hosted", "/boards/OW/OW-42?tenant=abc123", fixturesWithTenantLink);
    expect(await screen.findByText("Lab: t-abc123")).toBeInTheDocument();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/state/settings", expect.objectContaining({
      method: "PUT",
      body: JSON.stringify({ tenantId: "abc123" }),
    })));

    state = { ...state, settings: { tenantId: "abc123" } };
    await bootWorkbench("hosted", "/boards/OW/OW-42", fixturesWithTenantLink);
    expect(await screen.findByText("Lab: t-abc123")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tenant service" }))
      .toHaveAttribute("href", "https://t-abc123.demo.otterworks.app/api");
  });

  it("persists a static tenant selection across reloads", async () => {
    await bootWorkbench("static", "/boards/OW/OW-42?tenant=abc123");
    expect(localStorage.getItem("workbench.settings.v1")).toBe(JSON.stringify({ tenantId: "abc123" }));

    await bootWorkbench("static", "/boards/OW/OW-42");
    expect(await screen.findByText("Lab: t-abc123")).toBeInTheDocument();
  });

  it("persists a lab entered from the hosted header prompt", async () => {
    const fetchMock = stubHostedApi(() => ({ boards: null, chat: null, settings: null }));
    const promptMock = vi.fn().mockReturnValue("abc123");
    vi.stubGlobal("prompt", promptMock);

    await bootWorkbench("hosted", "/");
    fireEvent.click(await screen.findByRole("button", { name: "Set lab" }));

    expect(promptMock).toHaveBeenCalledWith("Lab ID");
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/state/settings", expect.objectContaining({
      method: "PUT",
      body: JSON.stringify({ tenantId: "abc123" }),
    })));
  });

  it("hydrates remote documents and writes through supported storage keys", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 });
    vi.stubGlobal("fetch", fetchMock);
    const storage = new RemoteStorage();
    await storage.hydrate({ boards: { issues: {} }, chat: null, settings: { tenantId: "lab-1" } });
    expect(JSON.parse(storage.getItem("workbench.boards.v1")!)).toEqual({ issues: {} });
    expect(storage.getItem("workbench.chat.v1")).toBeNull();
    expect(JSON.parse(storage.getItem("workbench.settings.v1")!)).toEqual({ tenantId: "lab-1" });

    storage.setItem("workbench.chat.v1", JSON.stringify([{ id: "message-1" }]));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/state/chat", expect.objectContaining({
      method: "PUT",
      headers: expect.objectContaining({ "X-Workbench-Request": "1" }),
      body: JSON.stringify([{ id: "message-1" }]),
    })));
  });

  it("resets remote state with only one delete request", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 });
    vi.stubGlobal("fetch", fetchMock);
    const storage = new RemoteStorage();
    storage.setItem("workbench.boards.v1", "{}");
    storage.removeItem("workbench.boards.v1");
    storage.clear();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls.filter(([url, options]) => url === "/api/state" && options?.method === "DELETE")).toHaveLength(1);
    expect(fetchMock.mock.calls[1]?.[1]?.headers).toEqual({ "X-Workbench-Request": "1" });
    expect(fetchMock.mock.calls.map(([, options]) => options?.method)).toEqual(["PUT", "DELETE"]);
  });

  it("marks the hosted reset fallback request with the CSRF header", () => {
    const fetchMock = vi.fn().mockImplementation(() => new Promise(() => undefined));
    vi.stubGlobal("fetch", fetchMock);
    render(
      <WorkbenchProvider value={{
        fixtures: baseFixtures,
        user: { sub: "alice", name: "Alice Attendee", email: "alice@example.com" },
        mode: "hosted",
        tenantId: "",
        setTenantId: () => undefined,
      }}>
        <ResetDemoButton />
      </WorkbenchProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Reset demo data" }));
    expect(fetchMock).toHaveBeenCalledWith("/api/state", expect.objectContaining({
      method: "DELETE",
      headers: { "X-Workbench-Request": "1" },
    }));
  });

  it("redirects expired PUT and DELETE sessions back to the current route", async () => {
    const assign = vi.fn();
    vi.stubGlobal("window", {
      location: {
        pathname: "/boards/OW/OW-42",
        search: "?view=history",
        assign,
      },
    });
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 401 });
    vi.stubGlobal("fetch", fetchMock);
    const storage = new RemoteStorage();
    storage.setItem("workbench.chat.v1", "[]");
    await vi.waitFor(() => expect(assign).toHaveBeenCalledTimes(1));

    await storage.reset();
    expect(assign).toHaveBeenCalledTimes(2);
    expect(assign).toHaveBeenNthCalledWith(
      1,
      "/auth/login?returnTo=%2Fboards%2FOW%2FOW-42%3Fview%3Dhistory",
    );
    expect(assign).toHaveBeenNthCalledWith(
      2,
      "/auth/login?returnTo=%2Fboards%2FOW%2FOW-42%3Fview%3Dhistory",
    );
    expect(fetchMock.mock.calls.map(([, options]) => options?.method)).toEqual(["PUT", "DELETE"]);
    expect(fetchMock.mock.calls[0]?.[1]?.headers).toEqual({
      "Content-Type": "application/json",
      "X-Workbench-Request": "1",
    });
    expect(fetchMock.mock.calls[1]?.[1]?.headers).toEqual({ "X-Workbench-Request": "1" });
  });

  it("attributes new chat, comment, and activity records to the hosted attendee", () => {
    const attendee = { id: "user-alice", name: "Alice Attendee", initials: "AA", title: "alice@example.com", kind: "human" as const };
    const hostedFixtures: Fixtures = {
      ...baseFixtures,
      currentUserId: attendee.id,
      people: [...baseFixtures.people, attendee],
    };
    const issue = hostedFixtures.issues.find((item) => item.key === "OW-42")!;
    const issueState = addIssueComment(hostedFixtures, issue.key, "Attendee comment");
    expect(issueState.issues[issue.key].comments[issueState.issues[issue.key].comments.length - 1]?.authorId).toBe(attendee.id);
    const moved = moveIssue(hostedFixtures, issue.key, issue.status === "done" ? "backlog" : "done");
    expect(moved.issues[issue.key].activity[moved.issues[issue.key].activity.length - 1]?.actorId).toBe(attendee.id);
    const messages = sendChatMessage(hostedFixtures, "general", "Attendee message");
    expect(messages[messages.length - 1]?.authorId).toBe(attendee.id);

    render(
      <WorkbenchProvider value={{
        fixtures: hostedFixtures,
        user: { sub: "alice", name: attendee.name, email: attendee.title },
        mode: "hosted",
        tenantId: "",
        setTenantId: () => undefined,
      }}>
        <MemoryRouter initialEntries={["/chat/general"]}>
          <ChannelPage channelId="general" />
        </MemoryRouter>
      </WorkbenchProvider>,
    );
    fireEvent.change(screen.getByLabelText("Message #general"), { target: { value: "A rendered attendee message" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(screen.getAllByText(attendee.name).length).toBeGreaterThan(0);
    expect(screen.getByText("A rendered attendee message")).toBeInTheDocument();
  });

  it("renders the hosted attendee's name for their board move activity", () => {
    const attendee = { id: "user-alice", name: "Alice Attendee", initials: "AA", title: "alice@example.com", kind: "human" as const };
    const hostedFixtures: Fixtures = {
      ...baseFixtures,
      currentUserId: attendee.id,
      people: [...baseFixtures.people, attendee],
    };
    const issue = hostedFixtures.issues.find((item) => item.key === "OW-42")!;

    render(
      <WorkbenchProvider value={{
        fixtures: hostedFixtures,
        user: { sub: "alice", name: attendee.name, email: attendee.title },
        mode: "hosted",
        tenantId: "",
        setTenantId: () => undefined,
      }}>
        <MemoryRouter initialEntries={[`/boards/${issue.projectKey}/${issue.key}`]}>
          <IssueDetail projectKey={issue.projectKey} issueKey={issue.key} />
        </MemoryRouter>
      </WorkbenchProvider>,
    );

    fireEvent.change(screen.getByRole("combobox", { name: "Move to" }), { target: { value: "done" } });
    const activityText = screen.getByText(attendee.name, { exact: true }).closest("li")?.textContent ?? "";
    expect(activityText).toContain(`${attendee.name} moved In review to Done`);
  });

  it("keeps the static fixture identity", () => {
    expect(baseFixtures.currentUserId).toBe("dwhitfield");
  });
});
