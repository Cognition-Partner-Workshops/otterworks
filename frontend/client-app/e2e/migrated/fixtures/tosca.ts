import { test as base, expect } from "@playwright/test";
import type { ToscaInstance } from "./types";
import { mockOtterWorksApi, mockAccessToken } from "./otterworks-api";

export type { ToscaInstance } from "./types";

export const test = base.extend<{
  toscaData: ToscaInstance;
  signedIn: boolean;
  otterworksSession: void;
}>({
  toscaData: [undefined as any, { option: true }],
  // Set `signedIn: false` for TestCases that exercise sign-in or registration.
  signedIn: [true, { option: true }],
  otterworksSession: [
    async ({ page, toscaData, signedIn }, use, testInfo) => {
      if (!toscaData) {
        throw new Error("The toscaData fixture must be provided.");
      }

      if (signedIn) {
        await page.addInitScript((accessToken) => {
          localStorage.setItem("otter_access_token", accessToken);
          localStorage.setItem("otter_refresh_token", "refresh-token");
        }, mockAccessToken(toscaData.workspace.user.id));
      }

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
