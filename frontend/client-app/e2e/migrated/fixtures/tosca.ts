import { test as base, expect } from "@playwright/test";
import type { ToscaInstance } from "./types";
import { mockOtterWorksApi } from "./otterworks-api";

export type { ToscaInstance } from "./types";

export const test = base.extend<{ toscaData: ToscaInstance; signedIn: void }>({
  toscaData: [undefined as any, { option: true }],
  signedIn: [
    async ({ page, toscaData }, use, testInfo) => {
      if (!toscaData) {
        throw new Error("The toscaData fixture must be provided.");
      }

      await page.addInitScript(() => {
        localStorage.setItem(
          "otter_access_token",
          "header.eyJzdWIiOiJ1c2VyLTEyMyJ9.sig",
        );
        localStorage.setItem("otter_refresh_token", "refresh-token");
      });

      const attachUnmockedApiCalls = await mockOtterWorksApi(
        page,
        toscaData.workspace,
        testInfo,
      );

      await use();
      await attachUnmockedApiCalls();
    },
    { auto: true },
  ],
});

export { expect };
