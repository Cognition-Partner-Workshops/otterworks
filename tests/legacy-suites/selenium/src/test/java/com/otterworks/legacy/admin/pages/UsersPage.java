package com.otterworks.legacy.admin.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public final class UsersPage extends BasePage {
  private final By heading = By.xpath("//h1[normalize-space()='User Management']");
  private final By searchInput = By.xpath("//input[@placeholder='Search by name or email']");
  private final By userRows = By.cssSelector("table.users-table tr.table-row");
  private final By roleSelect = By.xpath("//mat-label[normalize-space()='Role']/following::mat-select[1]");

  public UsersPage(WebDriver driver) {
    super(driver);
  }

  public void open() {
    open("/users");
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

  public int rowCount() {
    return driver.findElements(userRows).size();
  }

  public boolean hasRoleFilter() {
    return isPresent(roleSelect);
  }
}
