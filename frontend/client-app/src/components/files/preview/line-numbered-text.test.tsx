import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LineNumberedText } from "./line-numbered-text";

describe("LineNumberedText", () => {
  it("renders three gutter line numbers with a constant element count (AC-08, BDD-35)", () => {
    const { container, rerender } = render(<LineNumberedText text={"first\nsecond\nthird"} />);
    const initialElementCount = container.querySelectorAll("*").length;

    expect(screen.getByTestId("line-number-gutter").textContent).toBe("1\n2\n3");
    expect(screen.getByTestId("line-number-gutter")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByTestId("line-number-content").textContent).toBe("first\nsecond\nthird");
    expect(container.querySelectorAll("pre")).toHaveLength(2);

    rerender(<LineNumberedText text={Array.from({ length: 1_500 }, (_, index) => `line ${index + 1}`).join("\n")} />);

    expect(container.querySelectorAll("*")).toHaveLength(initialElementCount);
  });
});
