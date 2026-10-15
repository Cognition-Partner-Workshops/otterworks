import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { UserPresenceAvatars } from "./user-presence-avatars";
import type { Collaborator } from "@/types";

function collaborator(overrides: Partial<Collaborator>): Collaborator {
  return {
    userId: "u1",
    name: "Ada Lovelace",
    color: "#123456",
    isOnline: true,
    ...overrides,
  } as Collaborator;
}

describe("UserPresenceAvatars", () => {
  it("renders nothing when there are no collaborators", () => {
    const { container } = render(<UserPresenceAvatars collaborators={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows initials, online title and the online count", () => {
    render(
      <UserPresenceAvatars
        collaborators={[
          collaborator({ userId: "u1", name: "Ada Lovelace", isOnline: true }),
          collaborator({ userId: "u2", name: "Grace Hopper", isOnline: false }),
        ]}
      />,
    );
    expect(screen.getByTitle("Ada Lovelace (online)")).toHaveTextContent("AL");
    expect(screen.getByTitle("Grace Hopper")).toHaveTextContent("GH");
    expect(screen.getByText("1 online")).toBeInTheDocument();
  });

  it("collapses collaborators beyond maxVisible into a +N badge", () => {
    const many = Array.from({ length: 7 }, (_, i) =>
      collaborator({ userId: `u${i}`, name: `User ${i}` }),
    );
    render(<UserPresenceAvatars collaborators={many} maxVisible={3} />);
    expect(screen.getByText("+4")).toBeInTheDocument();
    expect(screen.getByText("7 online")).toBeInTheDocument();
  });

  it("uses the collaborator colour when provided", () => {
    render(
      <UserPresenceAvatars
        collaborators={[
          collaborator({ name: "Ada Lovelace", color: "#abcdef" }),
        ]}
      />,
    );
    expect(screen.getByTitle("Ada Lovelace (online)")).toHaveStyle({
      backgroundColor: "#abcdef",
    });
  });
});
