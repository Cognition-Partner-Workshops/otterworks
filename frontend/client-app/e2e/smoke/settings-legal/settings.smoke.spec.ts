import { test, expect } from "./settings-legal.fixtures";

test(
  "signed-in customer sees their own name and email in the Settings profile",
  { tag: ["@smoke", "@settings-legal"] },
  async ({ page, customer }) => {
    const main = page.getByRole("main");

    await test.step("Open Settings", async () => {
      await page.goto("/settings");
    });
    await test.step("Confirm the Settings heading", async () => {
      await expect(
        main.getByRole("heading", { name: "Settings", level: 1 }),
      ).toBeVisible();
    });
    await test.step("Confirm the customer's profile values", async () => {
      await expect(main.getByLabel("Full name")).toHaveValue(
        customer.displayName,
      );
      await expect(main.getByLabel("Email", { exact: true })).toHaveValue(
        customer.email,
      );
    });
    await test.step("Confirm notification preferences are available", async () => {
      await expect(
        main.getByRole("heading", { name: "Notification preferences" }),
      ).toBeVisible();
    });
  },
);

test(
  "signed-in customer saves a new display name from Settings",
  { tag: ["@smoke", "@settings-legal"] },
  async ({ page, customer }) => {
    test.fail(
      true,
      "PATCH /api/v1/auth/profile returns 500; auth-service only maps PUT /profile",
    );

    const main = page.getByRole("main");
    const newName = `${customer.displayName} Renamed`;

    await test.step("Open Settings and wait for the customer's profile", async () => {
      await page.goto("/settings");
      await expect(main.getByLabel("Full name")).toHaveValue(
        customer.displayName,
      );
    });
    await test.step("Save the new display name", async () => {
      await main.getByLabel("Full name").fill(newName);
      await main.getByRole("button", { name: "Save changes" }).click();
      await expect(main.getByText("Profile updated successfully.")).toBeVisible();
    });
    await test.step("Confirm the new name persists after reload", async () => {
      await page.reload();
      await expect(main.getByLabel("Full name")).toHaveValue(newName);
    });
  },
);
