import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { FileCard } from "./file-card";
import type { FileItem } from "@/types";

const file: FileItem = {
  id: "preview-file",
  name: "notes.txt",
  mimeType: "text/plain",
  size: 12,
  parentId: null,
  ownerId: "owner",
  ownerName: "",
  isFolder: false,
  path: "/notes.txt",
  sharedWith: [],
  tags: [],
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
  versions: [],
};

function CurrentPath() {
  return <output data-testid="current-path">{useLocation().pathname}</output>;
}

function renderCard(item: FileItem) {
  return render(
    <MemoryRouter initialEntries={["/files"]}>
      <CurrentPath />
      <Routes>
        <Route path="/files" element={<FileCard file={item} view="list" />} />
        <Route path="/files/:id" element={<CurrentPath />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("FileCard preview entry (AC-01, AC-02, BDD-01, BDD-02)", () => {
  it("shows Preview for a file and navigates to its detail route", () => {
    const { container } = renderCard(file);
    const menuButton = container.querySelectorAll("button")[1];
    fireEvent.click(menuButton);

    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(screen.getAllByTestId("current-path").at(-1)).toHaveTextContent("/files/preview-file");
  });

  it("does not show Preview for a folder", () => {
    const { container } = renderCard({ ...file, id: "folder", name: "Folder", isFolder: true });
    fireEvent.click(container.querySelectorAll("button")[1]);
    expect(screen.queryByRole("button", { name: "Preview" })).not.toBeInTheDocument();
  });
});
