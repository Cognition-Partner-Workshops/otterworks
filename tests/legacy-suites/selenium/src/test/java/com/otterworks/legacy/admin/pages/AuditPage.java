package com.otterworks.legacy.admin.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public final class AuditPage extends BasePage {
  private final By heading = By.xpath("//h1[normalize-space()='Audit Logs']");
  private final By searchInput = By.xpath("//input[@placeholder='Search by user, action, or resource']");
  private final By eventRows = By.cssSelector("table.audit-table tr.mat-mdc-row");
  private final By actionSelect = By.xpath("//mat-label[normalize-space()='Action']/following::mat-select[1]");

  public AuditPage(WebDriver driver) {
    super(driver);
  }

  public void open() {
    open("/audit");
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

  public int eventCount() {
    return driver.findElements(eventRows).size();
  }

  public boolean hasActionFilter() {
    return isPresent(actionSelect);
  }
}
