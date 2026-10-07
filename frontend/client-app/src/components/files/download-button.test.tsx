import { http, HttpResponse, delay } from "msw";
import { fireEvent, render, screen } from "@testing-library/react";
import { Toaster } from "react-hot-toast";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DownloadButton, getDownloadErrorMessage } from "./download-button";
import { billingServer as server } from "../../test-setup";

const STORAGE_URL = "http://storage.test/bucket/report.txt";

function renderButton(getDownloadUrl: () => Promise<string> = async () => STORAGE_URL) {
  return render(
    <>
      <DownloadButton fileName="report.txt" getDownloadUrl={getDownloadUrl} />
      <Toaster />
    </>
  );
}

describe("DownloadButton", () => {
  let clickSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    URL.createObjectURL = vi.fn(() => "blob:report");
    URL.revokeObjectURL = vi.fn();
    window.matchMedia ??= vi.fn(() => ({ matches: false }) as unknown as MediaQueryList);
  });

  afterEach(() => {
    clickSpy.mockRestore();
  });

  it("shows progress while downloading, then a done state that resets", async () => {
    server.use(
      http.get(STORAGE_URL, async () => {
        await delay(50);
        return new HttpResponse("hello", { headers: { "Content-Type": "text/plain" } });
      })
    );
    renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Download" }));

    const busy = await screen.findByRole("button", { name: "Downloading..." });
    expect(busy).toBeDisabled();
    expect(busy).toHaveAttribute("aria-busy", "true");
    expect(await screen.findByText("Downloading report.txt...")).toBeInTheDocument();

    const done = await screen.findByRole("button", { name: "Downloaded" });
    expect(done).toHaveAttribute("data-status", "done");
    // toast + polite live region
    expect(await screen.findAllByText("Downloaded report.txt")).toHaveLength(2);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(URL.createObjectURL).toHaveBeenCalled();

    expect(
      await screen.findByRole("button", { name: "Download" }, { timeout: 4000 })
    ).toBeEnabled();
  });

  it("shows a failed state with the storage error and allows retry", async () => {
    server.use(http.get(STORAGE_URL, () => new HttpResponse(null, { status: 403, statusText: "Forbidden" })));
    renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Download" }));

    const retry = await screen.findByRole("button", { name: "Retry download" });
    expect(retry).toHaveAttribute("data-status", "error");
    expect(retry).toHaveAttribute("title", "Download failed: Storage responded with 403 Forbidden");
    expect(
      await screen.findAllByText("Download failed: Storage responded with 403 Forbidden")
    ).toHaveLength(2);
    expect(clickSpy).not.toHaveBeenCalled();
    expect(retry).toBeEnabled();
  });

  it("surfaces the API error message when the download URL cannot be fetched", async () => {
    const apiError = Object.assign(new Error("Request failed with status code 404"), {
      response: { data: { error: "file not found" } },
    });
    renderButton(() => Promise.reject(apiError));
    fireEvent.click(screen.getByRole("button", { name: "Download" }));

    expect(await screen.findByRole("button", { name: "Retry download" })).toHaveAttribute(
      "title",
      "Download failed: file not found"
    );
  });

  it("reports unreachable storage as a failure", async () => {
    server.use(http.get(STORAGE_URL, () => HttpResponse.error()));
    renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Download" }));

    expect(await screen.findByRole("button", { name: "Retry download" })).toHaveAttribute(
      "title",
      "Download failed: Could not reach file storage"
    );
    expect(clickSpy).not.toHaveBeenCalled();
  });

  it("hands off to the browser when storage is reachable but blocks CORS reads", async () => {
    const realFetch = globalThis.fetch;
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((input, init) =>
        init?.mode === "no-cors"
          ? Promise.resolve(new Response(null, { status: 200 }))
          : Promise.reject(new TypeError("Failed to fetch"))
      );
    try {
      renderButton();
      fireEvent.click(screen.getByRole("button", { name: "Download" }));
      expect(await screen.findByRole("button", { name: "Downloaded" })).toBeInTheDocument();
      expect(await screen.findByText("Download of report.txt started")).toBeInTheDocument();
      expect(clickSpy).toHaveBeenCalledTimes(1);
    } finally {
      fetchSpy.mockRestore();
      globalThis.fetch = realFetch;
    }
  });
});

describe("getDownloadErrorMessage", () => {
  it("prefers the API error body, then the error message", () => {
    expect(getDownloadErrorMessage({ response: { data: { message: "expired" } } })).toBe("expired");
    expect(getDownloadErrorMessage(new Error("boom"))).toBe("boom");
    expect(getDownloadErrorMessage("??")).toBe("Unknown error");
  });
});
