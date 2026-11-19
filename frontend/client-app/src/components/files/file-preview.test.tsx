import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { ImageFilePreview } from "./file-preview";

afterEach(cleanup);

it("announces an image only as loaded after its load event and resets for a new URL", () => {
  const { rerender } = render(<ImageFilePreview fileName="Harbor" presignedUrl="http://localhost/one" />);
  fireEvent.load(screen.getByRole("img", { name: "Harbor" }));
  expect(screen.getByRole("img", { name: "Harbor preview loaded" })).toBeInTheDocument();
  rerender(<ImageFilePreview fileName="Harbor" presignedUrl="http://localhost/two" />);
  expect(screen.getByRole("img", { name: "Harbor" })).toBeInTheDocument();
});

it("shows the unavailable state with no URL", () => {
  render(<ImageFilePreview fileName="Harbor" />);
  expect(screen.getByText("Image preview not available")).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});

it("shows the unavailable state after an image error", () => {
  render(<ImageFilePreview fileName="Harbor" presignedUrl="http://localhost/broken" />);
  fireEvent.error(screen.getByRole("img"));
  expect(screen.getByText("Image preview not available")).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});
