package com.otterworks.legacy.admin.tests;

import com.otterworks.legacy.admin.pages.HealthPage;
import org.testng.Assert;
import org.testng.annotations.Test;

public final class HealthTest extends AdminTestBase {
  @Test
  public void healthPageShowsHeading() {
    HealthPage page = new HealthPage(driver);
    page.open();
    Assert.assertEquals(page.heading(), "System Health");
  }

  @Test
  public void healthSummaryIsDisplayed() {
    HealthPage page = new HealthPage(driver);
    page.open();
    Assert.assertTrue(page.hasHealthySummary());
  }

  @Test
  public void healthDataCanBeRefreshed() {
    HealthPage page = new HealthPage(driver);
    page.open();
    page.refresh();
    Assert.assertTrue(page.heading().contains("System Health"));
  }
}
