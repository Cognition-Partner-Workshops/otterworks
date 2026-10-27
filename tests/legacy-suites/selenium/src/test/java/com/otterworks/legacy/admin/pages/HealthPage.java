package com.otterworks.legacy.admin.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public final class HealthPage extends BasePage {
  private final By heading = By.xpath("//h1[normalize-space()='System Health']");
  private final By refreshButton = By.xpath("//button[.//mat-icon[normalize-space()='refresh']]");
  private final By healthySummary = By.cssSelector(".summary-card.healthy");
  private final By serviceCards = By.cssSelector(".service-card");

  public HealthPage(WebDriver driver) {
    super(driver);
  }

  public void open() {
    open("/health");
  }

  public String heading() {
    return readText(heading);
  }

  public boolean hasHealthySummary() {
    return isPresent(healthySummary);
  }

  public int serviceCount() {
    return driver.findElements(serviceCards).size();
  }

  public void refresh() {
    driver.findElement(refreshButton).click();
    pause();
  }
}
