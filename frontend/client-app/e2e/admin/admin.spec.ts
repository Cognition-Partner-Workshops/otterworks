import {
  test,
  expect,
  login,
  openUsers,
  userRows,
  userRow,
  chooseOption,
  searchUsers,
  openActions,
} from "./helpers";

const firstPageNames = [
  "Alice Morgan",
  "Ben Carter",
  "Chloe Patel",
  "Daniel Kim",
  "Emma Wilson",
];

test("login succeeds and opens the dashboard", async ({ page, routes }) => {
  await login(page, routes);
  expect(
    await page.evaluate(() => localStorage.getItem("ow_admin_token"))
  ).toBe("fixture-admin-token");
  await expect(page.getByText("Alice Morgan", { exact: true })).toBeVisible();
});

test("unauthenticated dashboard redirects to login", async ({
  page,
  routes,
}) => {
  await page.goto(routes("dashboard"));
  await expect(page).toHaveURL(routes("login"));
  await expect(
    page.getByRole("button", { name: "Sign In", exact: true })
  ).toBeVisible();
});

test("logout clears admin authentication and opens login", async ({
  page,
  routes,
}) => {
  await login(page, routes);
  await page.getByRole("button", { name: "User menu", exact: true }).click();
  await page.getByText("Logout", { exact: true }).click();
  await expect(page).toHaveURL(routes("login"));
  expect(
    await page.evaluate(() => [
      localStorage.getItem("ow_admin_token"),
      localStorage.getItem("ow_admin_user"),
    ])
  ).toEqual([null, null]);
});

test("dashboard has fixture stat labels, values and both chart titles", async ({
  page,
  routes,
}) => {
  await login(page, routes);
  const cards = page.getByTestId("admin-stat-card");
  await expect(cards).toHaveCount(4);
  for (const [label, value] of [
    ["Total Users", "14"],
    ["Active Documents", "0"],
    ["Storage Used", "6.6 GB"],
    ["Active Sessions", "8"],
  ]) {
    const card = cards.filter({ has: page.getByText(label, { exact: true }) });
    await expect(card.getByTestId("admin-stat-value")).toHaveText(value);
    await expect(card.getByText(/0%/)).toBeVisible();
  }
  await expect(page.getByText("User Signups", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Document Activity", { exact: true })
  ).toBeVisible();
});

test("users start with five rows in backend order", async ({
  page,
  routes,
}) => {
  await openUsers(page, routes);
  await expect(userRows(page)).toHaveCount(5);
  for (const [index, name] of firstPageNames.entries()) {
    await expect(
      userRows(page).nth(index).getByText(name, { exact: true })
    ).toBeVisible();
  }
  await expect(page.getByText("1 – 5 of 14", { exact: true })).toBeVisible();
});

test("page size ten and next, last, previous and first pagination", async ({
  page,
  routes,
}) => {
  await openUsers(page, routes);
  await chooseOption(
    page,
    page.getByRole("combobox", { name: /Items per page/ }),
    1
  );
  await expect(userRows(page)).toHaveCount(10);
  await expect(page.getByText("1 – 10 of 14", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Next page", exact: true }).click();
  await expect(userRows(page)).toHaveCount(4);
  await expect(userRow(page, "Keira Singh")).toBeVisible();
  await page.getByRole("button", { name: "First page", exact: true }).click();
  await page.getByRole("button", { name: "Last page", exact: true }).click();
  await expect(page.getByText("11 – 14 of 14", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Previous page", exact: true })
    .click();
  await expect(page.getByText("1 – 10 of 14", { exact: true })).toBeVisible();
});

test("search matches name or email but not department", async ({
  page,
  routes,
}) => {
  await openUsers(page, routes);
  await searchUsers(page, "  aLiCe  ");
  await expect(userRows(page)).toHaveCount(1);
  await expect(userRow(page, "Alice Morgan")).toBeVisible();
  await searchUsers(page, "ben.carter@");
  await expect(userRows(page)).toHaveCount(1);
  await expect(userRow(page, "Ben Carter")).toBeVisible();
  await searchUsers(page, "Engineering");
  await expect(userRows(page)).toHaveCount(0);
  await expect(page.getByText("0 of 0", { exact: true })).toBeVisible();
});

test("role filter uses exact role", async ({ page, routes }) => {
  await openUsers(page, routes);
  await chooseOption(
    page,
    page.getByRole("combobox", { name: /^Role(?: |$)/ }),
    2
  );
  await expect(userRows(page)).toHaveCount(5);
  await expect(
    userRows(page)
      .getByRole("cell")
      .filter({ hasText: /^editor$/ })
  ).toHaveCount(5);
  await expect(userRow(page, "Ben Carter")).toBeVisible();
  await expect(userRow(page, "Alice Morgan")).toHaveCount(0);
});

test("status filter uses exact status", async ({ page, routes }) => {
  await openUsers(page, routes);
  await chooseOption(
    page,
    page.getByRole("combobox", { name: /^Status(?: |$)/ }),
    2
  );
  await expect(userRows(page)).toHaveCount(3);
  await expect(userRow(page, "Chloe Patel")).toBeVisible();
  await expect(userRow(page, "Grace Chen")).toBeVisible();
  await expect(userRow(page, "Keira Singh")).toBeVisible();
});

test("role, status and search filters are ANDed", async ({ page, routes }) => {
  await openUsers(page, routes);
  await chooseOption(
    page,
    page.getByRole("combobox", { name: /^Role(?: |$)/ }),
    3
  );
  await chooseOption(
    page,
    page.getByRole("combobox", { name: /^Status(?: |$)/ }),
    2
  );
  await expect(userRows(page)).toHaveCount(1);
  await expect(userRow(page, "Chloe Patel")).toBeVisible();
  await searchUsers(page, "chloe.patel@");
  await expect(userRows(page)).toHaveCount(1);
  await searchUsers(page, "Alice");
  await expect(userRows(page)).toHaveCount(0);
});

test("Name sort cycles ascending and descending", async ({ page, routes }) => {
  await openUsers(page, routes);
  await page.getByRole("button", { name: "Name", exact: true }).click();
  await expect(
    userRows(page).first().getByText("Alice Morgan", { exact: true })
  ).toBeVisible();
  await page.getByRole("button", { name: "Name", exact: true }).click();
  await expect(
    userRows(page).first().getByText("Noah Clark", { exact: true })
  ).toBeVisible();
  await expect(
    userRows(page).nth(1).getByText("Maya Jones", { exact: true })
  ).toBeVisible();
});

test("row click keeps the user detail URL", async ({ page, routes }) => {
  await openUsers(page, routes);
  await userRow(page, "Alice Morgan").click();
  await expect(page).toHaveURL(routes("userDetail", "fixture-user-01"));
});

test("row menu items depend on active, suspended or pending status", async ({
  page,
  routes,
}) => {
  await openUsers(page, routes);
  for (const [name, action] of [
    ["Alice Morgan", "Suspend"],
    ["Chloe Patel", "Restore"],
    ["Daniel Kim", null],
  ] as const) {
    await openActions(page, name);
    await expect(
      page.getByRole("menuitem").filter({ hasText: "View Details" })
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem").filter({ hasText: "Delete" })
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem").filter({ hasText: "Suspend" })
    ).toHaveCount(action === "Suspend" ? 1 : 0);
    await expect(
      page.getByRole("menuitem").filter({ hasText: "Restore" })
    ).toHaveCount(action === "Restore" ? 1 : 0);
    await expect(page.getByRole("menuitem")).toHaveCount(action ? 3 : 2);
    await page.getByRole("menuitem").filter({ hasText: "Delete" }).click();
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
  }
});

test("last-row actions stay in the viewport and remain clickable after suspend", async ({
  page,
  routes,
}) => {
  await page.setViewportSize({ width: 1280, height: 600 });
  await openUsers(page, routes);
  await page.getByRole("button", { name: "Last page", exact: true }).click();
  await expect(page.getByText("11 – 14 of 14", { exact: true })).toBeVisible();
  await expect(userRows(page).last()).toContainText("Noah Clark");
  await openActions(page, "Noah Clark");
  await page.getByRole("menuitem").filter({ hasText: "Suspend" }).click();
  await page.getByRole("button", { name: "Suspend", exact: true }).click();
  await expect(userRow(page, "Alice Morgan")).toBeVisible();
  await page.getByRole("button", { name: "Last page", exact: true }).click();
  await openActions(page, "Noah Clark");
  await expect(page.getByRole("menuitem")).toHaveCount(3);
  for (const name of ["View Details", "Restore", "Delete"]) {
    const item = page.getByRole("menuitem").filter({ hasText: name });
    await expect(item).toBeVisible();
    await expect(item).toBeInViewport({ ratio: 1 });
  }
  await page.getByRole("menuitem").filter({ hasText: "Delete" }).click();
  await expect(page.getByRole("dialog")).toContainText("Delete User");
  await expect(page.getByRole("dialog")).toContainText(
    "permanently delete Noah Clark?"
  );
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await openActions(page, "Noah Clark");
  await page.getByRole("menuitem").filter({ hasText: "Restore" }).click();
  await expect(page.getByText(/Noah Clark has been restored/)).toBeVisible();
  await expect(userRow(page, "Alice Morgan")).toBeVisible();
  await page.getByRole("button", { name: "Last page", exact: true }).click();
  await openActions(page, "Noah Clark");
  await page.getByRole("menuitem").filter({ hasText: "View Details" }).click();
  await expect(page).toHaveURL(routes("userDetail", "fixture-user-14"));
});

test("suspend supports cancel and confirm, then shows snackbar and status", async ({
  page,
  routes,
}) => {
  await openUsers(page, routes);
  await openActions(page, "Alice Morgan");
  await page.getByRole("menuitem").filter({ hasText: "Suspend" }).click();
  await expect(page.getByRole("dialog")).toContainText("Suspend User");
  await expect(
    page.getByText("Are you sure you want to suspend Alice Morgan?", {
      exact: true,
    })
  ).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    userRow(page, "Alice Morgan").getByRole("cell").nth(2)
  ).toHaveText("active");
  await openActions(page, "Alice Morgan");
  await page.getByRole("menuitem").filter({ hasText: "Suspend" }).click();
  await page.getByRole("button", { name: "Suspend", exact: true }).click();
  await expect(page.getByText(/Alice Morgan has been suspended/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Dismiss", exact: true })
  ).toBeVisible();
  await expect(
    userRow(page, "Alice Morgan").getByRole("cell").nth(2)
  ).toHaveText("suspended");
});

test("restore immediately changes status without confirmation", async ({
  page,
  routes,
}) => {
  await openUsers(page, routes);
  await openActions(page, "Chloe Patel");
  await page.getByRole("menuitem").filter({ hasText: "Restore" }).click();
  await expect(page.getByText(/Chloe Patel has been restored/)).toBeVisible();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    userRow(page, "Chloe Patel").getByRole("cell").nth(2)
  ).toHaveText("active");
});

test("delete confirms permanent removal and updates count to thirteen", async ({
  page,
  routes,
}) => {
  await openUsers(page, routes);
  await openActions(page, "Alice Morgan");
  await page.getByRole("menuitem").filter({ hasText: "Delete" }).click();
  await expect(page.getByRole("dialog")).toContainText("Delete User");
  await expect(
    page.getByText(
      "Are you sure you want to permanently delete Alice Morgan? This action cannot be undone.",
      { exact: true }
    )
  ).toBeVisible();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByText(/Alice Morgan has been deleted/)).toBeVisible();
  await expect(userRow(page, "Alice Morgan")).toHaveCount(0);
  await expect(page.getByText("1 – 5 of 13", { exact: true })).toBeVisible();
});

test("users 500 keeps the spinner and hides the table", async ({
  page,
  routes,
}) => {
  await login(page, routes);
  await page.route("**/api/v1/admin/users", (route) =>
    route.fulfill({ status: 500, json: { error: "Fixture users failure" } })
  );
  const response = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/admin/users") &&
      response.status() === 500
  );
  await page.goto(routes("users"));
  await response;
  await expect(page.getByRole("progressbar")).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);
});
