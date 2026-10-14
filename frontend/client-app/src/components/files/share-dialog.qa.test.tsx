import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { SharedUser } from "@/types";

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/lib/api", () => ({
  filesApi: {
    updateSharePermission: vi.fn().mockResolvedValue(undefined),
    removeShare: vi.fn().mockResolvedValue(undefined),
  },
}));

import toast from "react-hot-toast";
import { filesApi } from "@/lib/api";
import { ShareDialog } from "./share-dialog";

const ownerId = "owner-1111";
const bob: SharedUser = { userId: "bob-2222-aaaa", name: "", email: "", permission: "view" };
const carol: SharedUser = { userId: "carol-3333-bbbb", name: "Carol", email: "carol@example.test", permission: "edit" };

function renderDialog(overrides: Partial<Parameters<typeof ShareDialog>[0]> = {}) {
  const props = {
    fileId: "file-123",
    fileName: "Budget.xlsx",
    ownerId,
    ownerName: "Alice",
    ownerEmail: "alice@example.test",
    sharedWith: [] as SharedUser[],
    onShare: vi.fn().mockResolvedValue(undefined),
    onClose: vi.fn(),
    ...overrides,
  };
  render(<ShareDialog {...props} />);
  return props;
}

describe("ShareDialog (QA)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the file name in the title", () => {
    renderDialog();
    expect(screen.getByRole("heading", { name: /Share .Budget\.xlsx./ })).toBeInTheDocument();
  });

  it("shows owner row and empty-state when nobody else has access", () => {
    renderDialog();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(screen.getByText("No one else has access yet")).toBeInTheDocument();
  });

  it("disables the Share button until an email is typed", () => {
    renderDialog();
    const shareBtn = screen.getByRole("button", { name: "Share" });
    expect(shareBtn).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText("Add people by email"), { target: { value: "bob@example.test" } });
    expect(shareBtn).toBeEnabled();
  });

  it("defaults the permission to view and calls onShare with trimmed email", async () => {
    const props = renderDialog();
    fireEvent.change(screen.getByPlaceholderText("Add people by email"), { target: { value: "  bob@example.test  " } });
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    await waitFor(() => expect(props.onShare).toHaveBeenCalledWith("bob@example.test", "view"));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Shared with bob@example.test"));
    expect(screen.getByPlaceholderText("Add people by email")).toHaveValue("");
  });

  it("passes the edit permission when Editor is selected", async () => {
    const props = renderDialog();
    fireEvent.change(screen.getByPlaceholderText("Add people by email"), { target: { value: "bob@example.test" } });
    const [newShareSelect] = screen.getAllByRole("combobox");
    fireEvent.change(newShareSelect, { target: { value: "edit" } });
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    await waitFor(() => expect(props.onShare).toHaveBeenCalledWith("bob@example.test", "edit"));
  });

  it("shares on Enter key", async () => {
    const props = renderDialog();
    const input = screen.getByPlaceholderText("Add people by email");
    fireEvent.change(input, { target: { value: "bob@example.test" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(props.onShare).toHaveBeenCalledTimes(1));
  });

  it("does not call onShare for whitespace-only email", () => {
    const props = renderDialog();
    const input = screen.getByPlaceholderText("Add people by email");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(props.onShare).not.toHaveBeenCalled();
  });

  it("shows an error toast and keeps the email when sharing fails", async () => {
    renderDialog({ onShare: vi.fn().mockRejectedValue(new Error("404")) });
    const input = screen.getByPlaceholderText("Add people by email");
    fireEvent.change(input, { target: { value: "ghost@example.test" } });
    fireEvent.click(screen.getByRole("button", { name: "Share" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Failed to share file"));
    expect(input).toHaveValue("ghost@example.test");
  });

  it("lists shared users with resolved names and their permission", () => {
    renderDialog({
      sharedWith: [bob, carol],
      resolvedUsers: { [bob.userId]: { name: "Bob Builder", email: "bob@example.test" } },
    });
    expect(screen.getByText("Bob Builder")).toBeInTheDocument();
    expect(screen.getByText("bob@example.test")).toBeInTheDocument();
    expect(screen.getByText("Carol")).toBeInTheDocument();
    const selects = screen.getAllByRole("combobox") as HTMLSelectElement[];
    // [0] = new-share select, [1] = bob, [2] = carol
    expect(selects[1].value).toBe("view");
    expect(selects[2].value).toBe("edit");
    expect(screen.queryByText("No one else has access yet")).not.toBeInTheDocument();
  });

  it("falls back to a userId prefix when the user cannot be resolved", () => {
    renderDialog({ sharedWith: [bob] });
    expect(screen.getByText(bob.userId.slice(0, 8))).toBeInTheDocument();
  });

  it("hides the owner from the shared-users list", () => {
    renderDialog({ sharedWith: [{ userId: ownerId, name: "Self", email: "", permission: "edit" }] });
    expect(screen.queryByText("Self")).not.toBeInTheDocument();
    expect(screen.getByText("No one else has access yet")).toBeInTheDocument();
  });

  it("calls onPermissionChange when a shared user's role changes", async () => {
    const onPermissionChange = vi.fn().mockResolvedValue(undefined);
    renderDialog({ sharedWith: [bob], onPermissionChange });
    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[1], { target: { value: "edit" } });
    await waitFor(() => expect(onPermissionChange).toHaveBeenCalledWith(bob.userId, "edit"));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Permission updated"));
  });

  it("falls back to filesApi.updateSharePermission without a handler", async () => {
    renderDialog({ sharedWith: [bob] });
    fireEvent.change(screen.getAllByRole("combobox")[1], { target: { value: "edit" } });
    await waitFor(() => expect(filesApi.updateSharePermission).toHaveBeenCalledWith("file-123", bob.userId, "edit"));
  });

  it("calls onRemoveAccess when the remove button is clicked", async () => {
    const onRemoveAccess = vi.fn().mockResolvedValue(undefined);
    renderDialog({ sharedWith: [bob], onRemoveAccess });
    fireEvent.click(screen.getByTitle("Remove access"));
    await waitFor(() => expect(onRemoveAccess).toHaveBeenCalledWith(bob.userId));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Access removed"));
  });

  it("falls back to filesApi.removeShare and reports failures", async () => {
    vi.mocked(filesApi.removeShare).mockRejectedValueOnce(new Error("boom"));
    renderDialog({ sharedWith: [bob] });
    fireEvent.click(screen.getByTitle("Remove access"));
    await waitFor(() => expect(filesApi.removeShare).toHaveBeenCalledWith("file-123", bob.userId));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Failed to remove access"));
  });

  it("Get link tab shows the file URL and restricted access by default", () => {
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: /Get link/ }));
    expect(screen.getByText(`${window.location.origin}/files/file-123`)).toBeInTheDocument();
    expect(screen.getByText("Only people with access can open this link")).toBeInTheDocument();
  });

  it("switching to 'Anyone with the link' updates the hint text", () => {
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: /Get link/ }));
    fireEvent.click(screen.getByRole("button", { name: /Anyone with the link/ }));
    expect(screen.getAllByText("Anyone with the link can view this file").length).toBeGreaterThanOrEqual(2);
  });

  it("copies the share link to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: /Get link/ }));
    fireEvent.click(screen.getByRole("button", { name: /Copy link/ }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/files/file-123`));
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });

  it("closes via the X button", () => {
    const props = renderDialog();
    const closeButtons = screen.getAllByRole("button").filter((b) => !b.textContent?.trim());
    fireEvent.click(closeButtons[0]);
    expect(props.onClose).toHaveBeenCalled();
  });
});
