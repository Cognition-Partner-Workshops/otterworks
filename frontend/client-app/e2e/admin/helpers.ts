import {
  test as base,
  expect,
  type Locator,
  type Page,
  type TestInfo,
} from "@playwright/test";

type AdminRoute = "login" | "dashboard" | "users" | "userDetail";

export function adminRoutes(testInfo: TestInfo) {
  const baseURL = testInfo.project.use.baseURL;
  const prefix = testInfo.project.metadata.pathPrefix as string;

  return (route: AdminRoute, id?: string) => {
    const paths = {
      login: "/login",
      dashboard: "",
      users: "/users",
      userDetail: `/users/${encodeURIComponent(id ?? "")}`,
    };
    return new URL(`${prefix}${paths[route]}` || "/", baseURL).href;
  };
}

export type AdminRoutes = ReturnType<typeof adminRoutes>;

export const test = base.extend<{ routes: AdminRoutes }>({
  routes: async ({}, use, testInfo) => {
    await use(adminRoutes(testInfo));
  },
});

test.beforeEach(async ({ request }) => {
  const port = process.env.FIXTURE_GATEWAY_PORT || "8099";
  const reset = await request.post(`http://127.0.0.1:${port}/__reset`);
  expect(reset.ok()).toBeTruthy();
});

export { expect };

export async function login(page: Page, routes: AdminRoutes) {
  await page.goto(routes("login"));
  await page.getByLabel("Email", { exact: true }).fill("admin@otterworks.dev");
  await page.getByLabel("Password", { exact: true }).fill("Admin123!");
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(page).toHaveURL(routes("dashboard"));
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true })
  ).toBeVisible();
}

export async function openUsers(page: Page, routes: AdminRoutes) {
  await login(page, routes);
  await page.goto(routes("users"));
  await expect(page.getByRole("table")).toBeVisible();
}

export function userRows(page: Page) {
  return page.getByRole("row").filter({ has: page.getByRole("cell") });
}

export function userRow(page: Page, name: string) {
  return userRows(page).filter({ has: page.getByText(name, { exact: true }) });
}

export async function chooseOption(
  page: Page,
  combobox: Locator,
  index: number
) {
  await combobox.click();
  await page.keyboard.press("Home");
  for (let step = 0; step < index; step++) {
    await page.keyboard.press("ArrowDown");
  }
  await page.keyboard.press("Enter");
}

export async function searchUsers(page: Page, value: string) {
  const search = page.getByPlaceholder("Search by name or email");
  await search.fill(value);
  await search.press("ArrowLeft");
}

export async function openActions(page: Page, name: string) {
  await userRow(page, name)
    .getByRole("button", { name: "User actions", exact: true })
    .click();
}
