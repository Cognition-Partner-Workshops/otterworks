package com.otterworks.legacy.admin.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public final class FeaturesPage extends BasePage {
  private final By heading = By.xpath("//h1[normalize-space()='Feature Flags']");
  private final By searchInput = By.xpath("//input[@placeholder='Search by name or description']");
  private final By featureCards = By.cssSelector(".flag-card");
  private final By firstToggle = By.cssSelector(".flag-card mat-slide-toggle");

  public FeaturesPage(WebDriver driver) {
    super(driver);
  }

  public void open() {
    open("/features");
  }

  public String heading() {
    return readText(heading);
  }

  public void search(String value) {
    enterText(searchInput, value);
    pause();
  }

  public String searchValue() {
    return driver.findElement(searchInput).getAttribute("value");
  }

  public int featureCount() {
    return driver.findElements(featureCards).size();
  }

  public void toggleFirstFeature() {
    driver.findElement(firstToggle).click();
    pause();
  }
}
