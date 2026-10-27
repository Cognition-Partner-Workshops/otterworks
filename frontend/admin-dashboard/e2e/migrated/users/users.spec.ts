import { LEGACY_SOURCE, UsersLegacyData, expect, test } from "./fixtures";
import { typeIntoFilter } from "../support/material";
import { legacyDetails } from "../support/traceability";

test.describe("Selenium UsersTest (migrated)", () => {
  test("SEL-UsersTest-userListShowsHeading userListShowsHeading", {
    ...legacyDetails({ suite: "selenium", id: "SEL-UsersTest-userListShowsHeading", group: "selenium-UsersTest", source: LEGACY_SOURCE, method: "userListShowsHeading" }),
  }, async ({ usersPage }) => {
    await test.step("SEL-UsersTest-userListShowsHeading-STEP-01 Open /users", async () => {
      await usersPage.open();
    });
    await test.step("SEL-UsersTest-userListShowsHeading-STEP-02 Assert heading text", async () => {
      await expect(usersPage.heading()).toHaveText(UsersLegacyData.heading);
    });
  });

  test("SEL-UsersTest-userSearchAcceptsText userSearchAcceptsText", {
    ...legacyDetails({ suite: "selenium", id: "SEL-UsersTest-userSearchAcceptsText", group: "selenium-UsersTest", source: LEGACY_SOURCE, method: "userSearchAcceptsText" }),
  }, async ({ usersPage }) => {
    await test.step("SEL-UsersTest-userSearchAcceptsText-STEP-01 Open /users", async () => {
      await usersPage.open();
    });
    await test.step("SEL-UsersTest-userSearchAcceptsText-STEP-02 Enter search text", async () => {
      await typeIntoFilter(usersPage.searchBox(), UsersLegacyData.searchText);
    });
    await test.step("SEL-UsersTest-userSearchAcceptsText-STEP-03 Assert search value", async () => {
      await expect(usersPage.searchBox()).toHaveValue(UsersLegacyData.searchText);
    });
  });

  test("SEL-UsersTest-roleFilterIsAvailable roleFilterIsAvailable", {
    ...legacyDetails({ suite: "selenium", id: "SEL-UsersTest-roleFilterIsAvailable", group: "selenium-UsersTest", source: LEGACY_SOURCE, method: "roleFilterIsAvailable" }),
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
