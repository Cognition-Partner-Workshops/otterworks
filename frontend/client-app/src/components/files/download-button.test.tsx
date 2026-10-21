import { http, HttpResponse, delay } from "msw";
import { fireEvent, render, screen } from "@testing-library/react";
import { Toaster } from "react-hot-toast";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DownloadButton, getDownloadErrorMessage } from "./download-button";
import { billingServer as server } from "../../test-setup";

const STORAGE_URL = "http://storage.test/bucket/report.txt?response-content-disposition=attachment";

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
  let clickedLinks: HTMLAnchorElement[];

  beforeEach(() => {
    clickedLinks = [];
    clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        clickedLinks.push(this);
      });
    window.matchMedia ??= vi.fn(() => ({ matches: false }) as unknown as MediaQueryList);
  });

  afterEach(() => {
    clickSpy.mockRestore();
  });

  it("shows progress, then a done state that resets", async () => {
    server.use(
      http.get("http://storage.test/bucket/report.txt", async () => {
        await delay(50);
        return new HttpResponse("hello");
      })
    );
    renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Download" }));

    const busy = await screen.findByRole("button", { name: "Downloading..." });
    expect(busy).toBeDisabled();
    expect(busy).toHaveAttribute("aria-busy", "true");
    expect(await screen.findByText("Downloading report.txt...")).toBeInTheDocument();

    const done = await screen.findByRole("button", { name: "Download started" });
    expect(done).toHaveAttribute("data-status", "done");
    // toast + polite live region
    expect(await screen.findAllByText("Download of report.txt started")).toHaveLength(2);
    expect(clickedLinks).toHaveLength(1);
    expect(clickedLinks[0].href).toBe(STORAGE_URL);
    expect(clickedLinks[0].download).toBe("report.txt");

    expect(
      await screen.findByRole("button", { name: "Download" }, { timeout: 4000 })
    ).toBeEnabled();
  });

  it("shows a failed state with the API error and allows retry", async () => {
    const apiError = Object.assign(new Error("Request failed with status code 404"), {
      response: { data: { error: "file not found" } },
    });
    const getUrl = vi.fn().mockRejectedValueOnce(apiError).mockResolvedValue(STORAGE_URL);
    server.use(http.get("http://storage.test/bucket/report.txt", () => new HttpResponse("hello")));
    renderButton(getUrl);
    fireEvent.click(screen.getByRole("button", { name: "Download" }));

    const retry = await screen.findByRole("button", { name: "Retry download" });
    expect(retry).toHaveAttribute("data-status", "error");
    expect(retry).toHaveAttribute("title", "Download failed: file not found");
    expect(await screen.findAllByText("Download failed: file not found")).toHaveLength(2);
    expect(clickedLinks).toHaveLength(0);

    fireEvent.click(retry);
    expect(await screen.findByRole("button", { name: "Download started" })).toBeInTheDocument();
    expect(clickedLinks).toHaveLength(1);
  });

  it("reports unreachable storage as a failure without starting a download", async () => {
    server.use(http.get("http://storage.test/bucket/report.txt", () => HttpResponse.error()));
    renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Download" }));

    expect(await screen.findByRole("button", { name: "Retry download" })).toHaveAttribute(
      "title",
      "Download failed: Could not reach file storage"
    );
    expect(clickedLinks).toHaveLength(0);
  });
});

describe("getDownloadErrorMessage", () => {
  it("prefers the API error body, then the error message", () => {
    expect(getDownloadErrorMessage({ response: { data: { message: "expired" } } })).toBe("expired");
    expect(getDownloadErrorMessage(new Error("boom"))).toBe("boom");
    expect(getDownloadErrorMessage("??")).toBe("Unknown error");
  });
});
