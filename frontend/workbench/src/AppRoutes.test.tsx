import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { AppRoutes } from "@/AppRoutes";
import { fixtures } from "@/fixtures/fixtures";
import { personFor } from "@/components/shared";
import { loadBoardState, moveIssue } from "@/stores/boardsStore";
import { loadChatMessages, sendChatMessage } from "@/stores/chatStore";
import { resetWorkbenchData } from "@/stores/resetStore";

function renderAt(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>);
}

beforeEach(() => localStorage.clear());

describe("Workbench routes", () => {
  it("renders the home route", () => {
    renderAt("/");
    expect(screen.getByRole("heading", { name: "OtterWorks Workbench" })).toBeInTheDocument();
  });

  it("renders the projects list", () => {
    renderAt("/boards");
    expect(screen.getByRole("heading", { name: "Projects" })).toBeInTheDocument();
    expect(screen.getByText(fixtures.projects[0].name)).toBeInTheDocument();
  });

  it("renders a project board", () => {
    const project = fixtures.projects.find((item) => item.key === "OW")!;
    renderAt(`/boards/${project.key}`);
    expect(screen.getByRole("heading", { name: project.name })).toBeInTheDocument();
  });

  it.each(["OW-42", "SEC-12", "MOD-11"])("renders issue %s from its record", (key) => {
    const issue = fixtures.issues.find((item) => item.key === key)!;
    renderAt(`/boards/${issue.projectKey}/${issue.key}`);
    expect(screen.getByRole("heading", { name: issue.title })).toBeInTheDocument();
  });

  it("renders a channel with its fixture authors and composer", () => {
    const channel = fixtures.channels.find((item) => item.id === "incidents")!;
    const message = fixtures.messages.find((item) => item.channelId === channel.id)!;
    const author = personFor(fixtures.people, message.authorId);
    renderAt(`/chat/${channel.id}`);
    expect(screen.getByRole("heading", { name: `#${channel.id}` })).toBeInTheDocument();
    expect(screen.getAllByText(author.name).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(`Message #${channel.id}`)).toBeInTheDocument();
  });

  it("renders a thread and its replies", () => {
    const parent = fixtures.messages.find((item) => item.id === "p1001")!;
    const author = personFor(fixtures.people, parent.authorId);
    renderAt(`/chat/${parent.channelId}/t/${parent.id}`);
    expect(screen.getByRole("heading", { name: "Thread" })).toBeInTheDocument();
    expect(screen.getAllByText(author.name).length).toBeGreaterThan(0);
    expect(screen.getByText(`${parent.replies.length} replies`)).toBeInTheDocument();
  });

  it("renders an incident record", () => {
    const record = fixtures.incidents.find((item) => item.number === "INC0010042")!;
    renderAt(`/itsm/incidents/${record.number}`);
    expect(screen.getByRole("heading", { name: record.shortDescription })).toBeInTheDocument();
    expect(screen.getAllByText(record.number).length).toBeGreaterThan(0);
  });

  it("renders a problem record", () => {
    const record = fixtures.problems.find((item) => item.number === "PRB0040008")!;
    renderAt(`/itsm/problems/${record.number}`);
    expect(screen.getByRole("heading", { name: record.shortDescription })).toBeInTheDocument();
  });

  it("renders a change record", () => {
    const record = fixtures.changes.find((item) => item.number === "CHG0030017")!;
    renderAt(`/itsm/changes/${record.number}`);
    expect(screen.getByRole("heading", { name: record.shortDescription })).toBeInTheDocument();
  });

  it("renders a service record", () => {
    const service = fixtures.services.find((item) => item.name === "document-service")!;
    renderAt(`/itsm/services/${service.name}`);
    expect(screen.getByRole("heading", { name: service.displayName })).toBeInTheDocument();
    expect(screen.getByText(service.supportNote)).toBeInTheDocument();
  });

  it("renders a not-found page for unknown routes", () => {
    renderAt("/unknown/workbench/route");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Return home" })).toHaveAttribute("href", "/");
  });
});

describe("Workbench persistence", () => {
  it("moves an issue between columns with drag and drop", () => {
    const issue = fixtures.issues.find((item) => item.key === "OW-42")!;
    const values = new Map<string, string>();
    const dataTransfer = {
      setData: (format: string, value: string) => values.set(format, value),
      getData: (format: string) => values.get(format) ?? "",
      effectAllowed: "none",
      dropEffect: "none",
    } as unknown as DataTransfer;
    renderAt(`/boards/${issue.projectKey}`);
    const card = screen.getByRole("link", { name: issue.key }).closest("article")!;
    const doneColumn = screen.getByRole("region", { name: "Done column" });

    fireEvent.dragStart(card, { dataTransfer });
    fireEvent.dragOver(doneColumn, { dataTransfer });
    fireEvent.drop(doneColumn, { dataTransfer });

    expect(within(doneColumn).getByText(issue.title)).toBeInTheDocument();
    expect(loadBoardState(fixtures).issues[issue.key].status).toBe("done");
  });

  it("moves an issue and keeps its column after remount", () => {
    const issue = fixtures.issues.find((item) => item.key === "OW-42")!;
    const detail = renderAt(`/boards/${issue.projectKey}/${issue.key}`);
    fireEvent.change(screen.getByRole("combobox", { name: "Move to" }), { target: { value: "in_progress" } });
    detail.unmount();

    renderAt(`/boards/${issue.projectKey}`);
    const inProgress = screen.getByRole("region", { name: "In progress column" });
    expect(within(inProgress).getByText(issue.title)).toBeInTheDocument();
  });

  it("keeps a new comment after remount", () => {
    const issue = fixtures.issues.find((item) => item.key === "OW-42")!;
    const commentText = `${issue.title} follow-up`;
    const detail = renderAt(`/boards/${issue.projectKey}/${issue.key}`);
    fireEvent.change(screen.getByLabelText("Add a comment"), { target: { value: commentText } });
    fireEvent.click(screen.getByRole("button", { name: "Add comment" }));
    expect(screen.getByText(commentText)).toBeInTheDocument();
    detail.unmount();

    renderAt(`/boards/${issue.projectKey}/${issue.key}`);
    expect(screen.getByText(commentText)).toBeInTheDocument();
  });

  it("keeps a chat composer message after remount", () => {
    const channel = fixtures.channels.find((item) => item.id === "incidents")!;
    const parent = fixtures.messages.find((item) => item.channelId === channel.id)!;
    const messageText = `Follow-up for ${parent.id}`;
    const channelView = renderAt(`/chat/${channel.id}`);
    fireEvent.change(screen.getByLabelText(`Message #${channel.id}`), { target: { value: messageText } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(screen.getByText(messageText)).toBeInTheDocument();
    channelView.unmount();

    renderAt(`/chat/${channel.id}`);
    expect(screen.getByText(messageText)).toBeInTheDocument();
  });

  it("restores fixture data when demo storage is reset", () => {
    const issue = fixtures.issues.find((item) => item.key === "OW-42")!;
    const parent = fixtures.messages.find((item) => item.id === "p1001")!;
    moveIssue(fixtures, issue.key, "done");
    sendChatMessage(fixtures, parent.channelId, "Temporary demo message");
    resetWorkbenchData();

    expect(loadBoardState(fixtures).issues[issue.key].status).toBe(issue.status);
    expect(loadChatMessages(fixtures).map((message) => message.id)).toEqual(fixtures.messages.map((message) => message.id));
  });
});

describe("clone smoke checks", () => {
  it("shows all five board columns", () => {
    renderAt("/boards/OW");
    for (const label of ["Backlog", "Selected", "In progress", "In review", "Done"]) {
      expect(screen.getByRole("heading", { name: label })).toBeInTheDocument();
    }
  });

  it("shows chat messages and a composer", () => {
    const channel = fixtures.channels[0];
    const message = fixtures.messages.find((item) => item.channelId === channel.id)!;
    renderAt(`/chat/${channel.id}`);
    expect(screen.getAllByText(personFor(fixtures.people, message.authorId).name).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(`Message #${channel.id}`)).toBeInTheDocument();
  });

  it("lists each service fixture", () => {
    renderAt("/itsm/services");
    expect(screen.getAllByRole("row")).toHaveLength(fixtures.services.length + 1);
  });
});
