import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChannelPage } from "@/pages/ChatPage";
import { fixtures as baseFixtures } from "@/fixtures/fixtures";
import type { Fixtures } from "@/fixtures/types";
import { WorkbenchProvider } from "@/WorkbenchContext";
import { isValidTenantId, tenantUrl } from "@/tenant";
import { RemoteStorage, setWorkbenchStorage } from "@/stores/workbenchStorage";
import { addIssueComment, loadBoardState, moveIssue } from "@/stores/boardsStore";
import { sendChatMessage } from "@/stores/chatStore";

beforeEach(() => {
  localStorage.clear();
  setWorkbenchStorage(localStorage);
});

afterEach(() => {
  vi.unstubAllGlobals();
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
    expect(fetchMock.mock.calls.map(([, options]) => options?.method)).toEqual(["PUT", "DELETE"]);
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

  it("keeps the static fixture identity", () => {
    expect(baseFixtures.currentUserId).toBe("dwhitfield");
  });
});
