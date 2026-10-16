import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { filesApi } from "@/lib/api";
import { usePreviewUrl } from "./use-preview-url";
import type { ReactNode } from "react";

vi.mock("@/lib/api", () => ({
  filesApi: {
    getDownloadUrl: vi.fn(),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("usePreviewUrl (AC-28, AC-30)", () => {
  beforeEach(() => vi.resetAllMocks());

  it("refreshes a failed presigned URL once and returns the new URL (AC-28)", async () => {
    vi.mocked(filesApi.getDownloadUrl)
      .mockRejectedValueOnce({ isAxiosError: true, response: { status: 403 } })
      .mockResolvedValueOnce("https://storage/refreshed");
    const { result } = renderHook(() => usePreviewUrl("file-1"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.error).toBeTruthy());

    await expect(result.current.refresh()).resolves.toBe("https://storage/refreshed");
    expect(filesApi.getDownloadUrl).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(result.current.url).toBe("https://storage/refreshed"));
  });

  it("preserves the second failure for the caller to render (AC-28)", async () => {
    vi.mocked(filesApi.getDownloadUrl).mockRejectedValue({
      isAxiosError: true,
      response: { status: 403 },
    });
    const { result } = renderHook(() => usePreviewUrl("file-2"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.error).toBeTruthy());

    await expect(result.current.refresh()).rejects.toBeTruthy();
    expect(filesApi.getDownloadUrl).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(result.current.error).toBeTruthy());
  });

  it("exposes an unavailable state for 404 responses (AC-30)", async () => {
    vi.mocked(filesApi.getDownloadUrl).mockRejectedValue({
      isAxiosError: true,
      response: { status: 404 },
    });
    const { result } = renderHook(() => usePreviewUrl("missing-file"), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.notFound).toBe(true));
  });
});
