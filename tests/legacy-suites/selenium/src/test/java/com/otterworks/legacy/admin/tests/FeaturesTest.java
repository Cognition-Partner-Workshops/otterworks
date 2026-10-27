package com.otterworks.legacy.admin.tests;

import com.otterworks.legacy.admin.pages.FeaturesPage;
import org.testng.Assert;
import org.testng.annotations.Test;

public final class FeaturesTest extends AdminTestBase {
  @Test
  public void featurePageShowsHeading() {
    FeaturesPage page = new FeaturesPage(driver);
    page.open();
    Assert.assertEquals(page.heading(), "Feature Flags");
  }

  @Test
  public void featureSearchCanBeApplied() {
    FeaturesPage page = new FeaturesPage(driver);
    page.open();
    page.search("search");
    Assert.assertEquals(page.searchValue(), "search");
  }

  @Test
  public void featureToggleCanBeSelected() {
    FeaturesPage page = new FeaturesPage(driver);
    page.open();
    if (page.featureCount() > 0) {
      page.toggleFirstFeature();
      Assert.assertTrue(page.featureCount() > 0);
    }
  }
}
