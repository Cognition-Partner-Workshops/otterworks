import { LEGACY_SOURCE, UsersLegacyData, expect, test } from "./fixtures";

const TAG = "@selenium-UsersTest";

test.describe("Selenium UsersTest (migrated)", () => {
  test("SEL-UsersTest-userListShowsHeading userListShowsHeading", {
    tag: ["@SEL-UsersTest-userListShowsHeading", TAG],
    annotation: { type: "selenium", description: `${LEGACY_SOURCE}#userListShowsHeading` },
  }, async ({ usersPage }) => {
    await test.step("SEL-UsersTest-userListShowsHeading-STEP-01 Open /users", async () => {
      await usersPage.open();
    });
    await test.step("SEL-UsersTest-userListShowsHeading-STEP-02 Assert heading text", async () => {
      await expect(usersPage.heading()).toHaveText(UsersLegacyData.heading);
    });
  });

  test("SEL-UsersTest-userSearchAcceptsText userSearchAcceptsText", {
    tag: ["@SEL-UsersTest-userSearchAcceptsText", TAG],
    annotation: { type: "selenium", description: `${LEGACY_SOURCE}#userSearchAcceptsText` },
  }, async ({ usersPage }) => {
    await test.step("SEL-UsersTest-userSearchAcceptsText-STEP-01 Open /users", async () => {
      await usersPage.open();
    });
    await test.step("SEL-UsersTest-userSearchAcceptsText-STEP-02 Enter search text", async () => {
      await usersPage.searchBox().fill(UsersLegacyData.searchText);
    });
    await test.step("SEL-UsersTest-userSearchAcceptsText-STEP-03 Assert search value", async () => {
      await expect(usersPage.searchBox()).toHaveValue(UsersLegacyData.searchText);
    });
  });

  test("SEL-UsersTest-roleFilterIsAvailable roleFilterIsAvailable", {
    tag: ["@SEL-UsersTest-roleFilterIsAvailable", TAG],
    annotation: { type: "selenium", description: `${LEGACY_SOURCE}#roleFilterIsAvailable` },
  }, async ({ usersPage }) => {
    await test.step("SEL-UsersTest-roleFilterIsAvailable-STEP-01 Open /users", async () => {
      await usersPage.open();
    });
    await test.step("SEL-UsersTest-roleFilterIsAvailable-STEP-02 Open Role filter", async () => {
      await usersPage.roleFilter().click();
    });
    await test.step("SEL-UsersTest-roleFilterIsAvailable-STEP-03 Assert role options", async () => {
      await expect(usersPage.roleOptions()).toHaveText([...UsersLegacyData.roleOptions]);
    });
  });
});
