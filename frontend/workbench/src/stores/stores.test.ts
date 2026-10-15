import { beforeEach, describe, expect, it } from "vitest";
import { fixtures } from "@/fixtures/fixtures";
import { addIssueComment, loadBoardState, moveIssue } from "@/stores/boardsStore";
import { loadChatMessages, sendChatMessage } from "@/stores/chatStore";
import { resetWorkbenchData } from "@/stores/resetStore";

beforeEach(() => localStorage.clear());

describe("board store", () => {
  it("persists issue status changes and activity", () => {
    const issue = fixtures.issues.find((item) => item.key === "OW-42")!;
    moveIssue(fixtures, issue.key, "done", localStorage, "2026-10-14T12:00:00Z");

    const saved = loadBoardState(fixtures).issues[issue.key];
    expect(saved.status).toBe("done");
    expect(saved.activity[saved.activity.length - 1]?.actorId).toBe(fixtures.currentUserId);
  });

  it("persists comments and an activity entry", () => {
    const issue = fixtures.issues.find((item) => item.key === "OW-42")!;
    const body = `${issue.title} follow-up`;
    addIssueComment(fixtures, issue.key, body, localStorage, "2026-10-14T12:00:00Z");

    const saved = loadBoardState(fixtures).issues[issue.key];
    expect(saved.comments[saved.comments.length - 1]?.body).toBe(body);
    expect(saved.activity[saved.activity.length - 1]?.text).toBe("Added a comment");
  });
});

describe("chat store", () => {
  it("persists new channel messages", () => {
    const channel = fixtures.channels.find((item) => item.id === "incidents")!;
    const text = `Update for ${channel.id}`;
    sendChatMessage(fixtures, channel.id, text, undefined, localStorage, "2026-10-14T12:00:00Z");

    const saved = loadChatMessages(fixtures).find((message) => message.text === text);
    expect(saved?.authorId).toBe(fixtures.currentUserId);
    expect(saved?.channelId).toBe(channel.id);
  });

  it("clears both stores and returns fixture data", () => {
    const issue = fixtures.issues.find((item) => item.key === "OW-42")!;
    const channel = fixtures.channels.find((item) => item.id === "incidents")!;
    moveIssue(fixtures, issue.key, "done");
    sendChatMessage(fixtures, channel.id, "Temporary demo message");
    resetWorkbenchData();

    expect(loadBoardState(fixtures).issues[issue.key].status).toBe(issue.status);
    expect(loadChatMessages(fixtures).map((message) => message.id)).toEqual(fixtures.messages.map((message) => message.id));
  });
});
