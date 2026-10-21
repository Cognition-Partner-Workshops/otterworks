import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./confirm-dialog";

function renderDialog(props: Partial<Parameters<typeof ConfirmDialog>[0]> = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(
    <ConfirmDialog
      open
      title="Delete permanently?"
      description={<>&ldquo;report.txt&rdquo; will be permanently deleted.</>}
      confirmLabel="Delete permanently"
      variant="destructive"
      onConfirm={onConfirm}
      onCancel={onCancel}
      {...props}
    />
  );
  return { onConfirm, onCancel };
}

describe("ConfirmDialog", () => {
  it("renders nothing when closed", () => {
    renderDialog({ open: false });
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("names the item and marks the confirm button as destructive", () => {
    renderDialog();
    const dialog = screen.getByRole("alertdialog", { name: "Delete permanently?" });
    expect(dialog).toHaveAccessibleDescription(/report\.txt.*permanently deleted/);
    const confirm = screen.getByRole("button", { name: "Delete permanently" });
    expect(confirm).toHaveAttribute("data-variant", "destructive");
    expect(confirm).toHaveClass("bg-red-600");
  });

  it("uses a plain dialog role for non-destructive confirms", () => {
    renderDialog({ variant: "default" });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete permanently" })).toHaveAttribute(
      "data-variant",
      "default"
    );
  });

  it("focuses Cancel first and keeps Tab focus inside the dialog", () => {
    renderDialog();
    const cancel = screen.getByRole("button", { name: "Cancel" });
    const confirm = screen.getByRole("button", { name: "Delete permanently" });
    expect(cancel).toHaveFocus();

    confirm.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(cancel).toHaveFocus();

    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(confirm).toHaveFocus();
  });

  it("confirms only from the destructive button", () => {
    const { onConfirm, onCancel } = renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Delete permanently" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("cancels on Escape", () => {
    const { onConfirm, onCancel } = renderDialog();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("returns focus to the trigger when it closes", () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();
    const { rerender } = render(
      <ConfirmDialog open title="t" description="d" onConfirm={() => {}} onCancel={() => {}} />
    );
    expect(trigger).not.toHaveFocus();
    rerender(
      <ConfirmDialog open={false} title="t" description="d" onConfirm={() => {}} onCancel={() => {}} />
    );
    expect(trigger).toHaveFocus();
    trigger.remove();
  });
});
