import { readFileSync } from "node:fs";
import path from "node:path";
import { test, expect } from "./fixtures/signed-in";

const APP_VERSION: string = JSON.parse(
  readFileSync(path.join(__dirname, "..", "package.json"), "utf8"),
).version;

test.use({ account: "signedOut" });

// OTD-13 corporate rebrand — see docs/bdd/otd13-corporate-rebrand-bdd.md
// Landing content is independent of authentication.
test.describe("Landing Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  // AC-01 / BDD-01
  test("displays the corporate hero with the otter logo", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "OtterWorks", exact: true, level: 1 })).toBeVisible();
    const logos = page.getByAltText("OtterWorks logo");
    await expect(logos).toHaveCount(2); // header + hero
    for (const logo of await logos.all()) {
      await expect(logo).toBeVisible();
    }
    await expect(page.getByText("Enterprise retail products for otters", { exact: true })).toBeVisible();
  });

  test("shows Sign In and Create Account CTAs", async ({ page }) => {
    // Header nav and hero both carry the pair.
    const signIn = page.getByRole("link", { name: "Sign In" });
    const createAccount = page.getByRole("link", { name: "Create Account" });
    await expect(signIn).toHaveCount(2);
    await expect(createAccount).toHaveCount(2);
    for (const link of await signIn.all()) {
      await expect(link).toHaveAttribute("href", "/login");
    }
    for (const link of await createAccount.all()) {
      await expect(link).toHaveAttribute("href", "/register");
    }
  });

  // AC-03 / BDD-07
  test("renders all corporate identity sections", async ({ page }) => {
    for (const title of ["Our Story", "Leadership", "Departments", "Products", "Newsroom", "Careers"]) {
      await expect(page.getByRole("heading", { name: title, exact: true, level: 2 })).toBeVisible();
    }
  });

  test("Sign In link navigates to /login", async ({ page }) => {
    await page.getByRole("navigation").getByRole("link", { name: "Sign In" }).click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  test("Create Account link navigates to /register", async ({ page }) => {
    await page.getByRole("navigation").getByRole("link", { name: "Create Account" }).click();
    await expect(page).toHaveURL(/\/register$/);
    await expect(page.getByRole("button", { name: "Create account" })).toBeVisible();
  });

  // AC-02c / BDD-06
  test("corporate footer shows company, version and legal links", async ({ page }) => {
    await expect(page.getByText("© OtterWorks, Inc.", { exact: true })).toBeVisible();
    await expect(page.getByText(`v${APP_VERSION}`, { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Terms", exact: true })).toHaveAttribute("href", "/terms");
    await expect(page.getByRole("link", { name: "Privacy", exact: true })).toHaveAttribute("href", "/privacy");
  });

  // AC-02c / BDD-06
  test("Terms and Privacy static pages are reachable from the footer", async ({ page }) => {
    await test.step("Footer Terms link opens the Terms of Service", async () => {
      await page.getByRole("link", { name: "Terms", exact: true }).click();
      await expect(page).toHaveURL(/\/terms$/);
      await expect(page.getByRole("heading", { name: "Terms of Service" })).toBeVisible();
    });
    await test.step("Footer Privacy link opens the Privacy Policy", async () => {
      await page.goto("/");
      await page.getByRole("link", { name: "Privacy", exact: true }).click();
      await expect(page).toHaveURL(/\/privacy$/);
      await expect(page.getByRole("heading", { name: "Privacy Policy" })).toBeVisible();
    });
  });
});
