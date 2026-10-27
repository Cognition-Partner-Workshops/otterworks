package com.otterworks.legacy.admin.tests;

import com.otterworks.legacy.admin.pages.AuditPage;
import org.testng.Assert;
import org.testng.annotations.Test;

public final class AuditTest extends AdminTestBase {
  @Test
  public void auditPageShowsHeading() {
    AuditPage page = new AuditPage(driver);
    page.open();
    Assert.assertEquals(page.heading(), "Audit Logs");
  }

  @Test
  public void auditSearchAcceptsText() {
    AuditPage page = new AuditPage(driver);
    page.open();
    page.search("document");
    Assert.assertEquals(page.searchValue(), "document");
  }

  @Test
  public void actionFilterIsAvailable() {
    AuditPage page = new AuditPage(driver);
    page.open();
    Assert.assertTrue(page.hasActionFilter());
  }
}
