import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Collaborator } from "@/types";
import { UserPresenceAvatars } from "./user-presence-avatars";
import { generateColor, getInitials } from "@/lib/utils";

type Listener = (arg: unknown) => void;

const providerInstances: FakeProvider[] = [];

class FakeProvider {
  url: string;
  room: string;
  opts: { params?: Record<string, string> };
  listeners: Record<string, Listener[]> = {};
  destroyed = false;
  awareness = {
    setLocalStateField: vi.fn(),
    getStates: () => new Map(),
    on: vi.fn(),
    off: vi.fn(),
    states: new Map(),
    clientID: 1,
  };
  constructor(url: string, room: string, _doc: unknown, opts: { params?: Record<string, string> }) {
    this.url = url;
    this.room = room;
    this.opts = opts;
    providerInstances.push(this);
  }
  on(event: string, cb: Listener) {
    (this.listeners[event] ||= []).push(cb);
  }
  off() {}
  emit(event: string, arg: unknown) {
    (this.listeners[event] || []).forEach((cb) => cb(arg));
  }
  destroy() {
    this.destroyed = true;
  }
}

vi.mock("y-websocket", () => ({ WebsocketProvider: FakeProvider }));
vi.mock("@tiptap/extension-collaboration-cursor", () => ({
  default: { configure: () => ({ name: "collaborationCursor", type: "extension", config: {} }) },
}));

function collaborator(overrides: Partial<Collaborator> = {}): Collaborator {
  return {
    userId: "u-1",
    name: "Alice Smith",
    isOnline: true,
    ...overrides,
  } as Collaborator;
}

describe("QA collaboration: presence helpers", () => {
  it("generateColor is deterministic per user id", () => {
    expect(generateColor("user-123")).toBe(generateColor("user-123"));
  });

  it("generateColor always returns a palette hex colour", () => {
    for (const seed of ["", "a", "anon", "f81d4fae-7dec-11d0-a765-00a0c91e6bf6", "🙂"]) {
      expect(generateColor(seed)).toMatch(/^#[0-9a-f]{6}$/);
    }
  });

  it("generateColor spreads different users across several colours", () => {
    const colors = new Set(Array.from({ length: 40 }, (_, i) => generateColor(`user-${i}`)));
    expect(colors.size).toBeGreaterThanOrEqual(4);
  });

  it("getInitials uses the first two words, upper-cased", () => {
    expect(getInitials("alice smith")).toBe("AS");
    expect(getInitials("Mary Jane Watson")).toBe("MJ");
    expect(getInitials("Bob")).toBe("B");
  });
});

describe("QA collaboration: UserPresenceAvatars", () => {
  it("renders nothing without collaborators", () => {
    const { container } = render(<UserPresenceAvatars collaborators={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders initials, online title and online count", () => {
    render(
      <UserPresenceAvatars
        collaborators={[
          collaborator(),
          collaborator({ userId: "u-2", name: "Bob Jones", isOnline: false }),
        ]}
      />
    );
    expect(screen.getByTitle("Alice Smith (online)")).toHaveTextContent("AS");
    expect(screen.getByTitle("Bob Jones")).toHaveTextContent("BJ");
    expect(screen.getByText("1 online")).toBeInTheDocument();
  });

  it("collapses collaborators beyond maxVisible into a +N badge", () => {
    const many = Array.from({ length: 7 }, (_, i) => collaborator({ userId: `u-${i}`, name: `User ${i}` }));
    render(<UserPresenceAvatars collaborators={many} maxVisible={3} />);
    expect(screen.getByText("+4")).toBeInTheDocument();
    expect(screen.getByText("7 online")).toBeInTheDocument();
  });

  it("uses the collaborator colour when provided, else a generated one", () => {
    render(
      <UserPresenceAvatars
        collaborators={[
          collaborator({ color: "#123456" }),
          collaborator({ userId: "u-9", name: "Zed Zero", color: undefined }),
        ]}
      />
    );
    expect(screen.getByTitle("Alice Smith (online)")).toHaveStyle({ backgroundColor: "#123456" });
    const generated = generateColor("u-9");
    expect(screen.getByTitle("Zed Zero (online)").getAttribute("style")).toContain(
      `background-color: ${hexToRgb(generated)}`
    );
  });
});

function hexToRgb(hex: string): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
}

describe("QA collaboration: CollaborativeEditor websocket wiring", () => {
  beforeEach(() => {
    providerInstances.length = 0;
    localStorage.setItem("otter_access_token", "qa-token");
    vi.unstubAllEnvs();
  });
  afterEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  async function renderEditor(documentId = "doc-42") {
    const { CollaborativeEditor } = await import("./collaborative-editor");
    const utils = render(<CollaborativeEditor documentId={documentId} />);
    await screen.findByTitle("Bold");
    return utils;
  }

  it("joins the per-document Yjs room with the access token", async () => {
    await renderEditor("doc-42");
    const provider = providerInstances[0];
    expect(provider.room).toBe("document-doc-42");
    expect(provider.opts.params).toEqual({ token: "qa-token" });
  });

  it("defaults to the collab-service Yjs port 8084 when VITE_COLLAB_WS_URL is unset", async () => {
    vi.stubEnv("VITE_COLLAB_WS_URL", "");
    await renderEditor();
    expect(providerInstances[0].url).toBe("ws://localhost:8084");
  });

  it("honours VITE_COLLAB_WS_URL", async () => {
    vi.stubEnv("VITE_COLLAB_WS_URL", "wss://collab.example.test");
    await renderEditor();
    expect(providerInstances[0].url).toBe("wss://collab.example.test");
  });

  it("shows Reconnecting, Offline and saved states from provider status/sync events", async () => {
    await renderEditor();
    const provider = providerInstances[providerInstances.length - 1];
    expect(screen.getByText("Reconnecting…")).toBeInTheDocument();
    act(() => provider.emit("status", { status: "connected" }));
    expect(screen.getByText("Saving…")).toBeInTheDocument();
    act(() => provider.emit("sync", true));
    expect(screen.getByText("All changes saved")).toBeInTheDocument();
    act(() => provider.emit("status", { status: "disconnected" }));
    expect(screen.getByText("Offline")).toBeInTheDocument();
    act(() => provider.emit("status", { status: "connecting" }));
    expect(screen.getByText("Reconnecting…")).toBeInTheDocument();
    act(() => provider.emit("status", { status: "connected" }));
    expect(screen.getByText("All changes saved")).toBeInTheDocument();
  });

  it("destroys the provider on unmount (no leaked websocket)", async () => {
    const { unmount } = await renderEditor();
    const created = [...providerInstances];
    unmount();
    expect(created.length).toBeGreaterThan(0);
    expect(created.every((p) => p.destroyed)).toBe(true);
  });
});
