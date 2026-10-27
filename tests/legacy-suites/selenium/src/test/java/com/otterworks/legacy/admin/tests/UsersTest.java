package com.otterworks.legacy.admin.tests;

import com.otterworks.legacy.admin.pages.UsersPage;
import org.testng.Assert;
import org.testng.annotations.Test;

public final class UsersTest extends AdminTestBase {
  @Test
  public void userListShowsHeading() {
    UsersPage page = new UsersPage(driver);
    page.open();
    Assert.assertEquals(page.heading(), "User Management");
  }

  @Test
  public void userSearchAcceptsText() {
    UsersPage page = new UsersPage(driver);
    page.open();
    page.search("alex");
    Assert.assertEquals(page.searchValue(), "alex");
  }

  @Test
  public void roleFilterIsAvailable() {
    UsersPage page = new UsersPage(driver);
    page.open();
    Assert.assertTrue(page.hasRoleFilter());
  }
}
