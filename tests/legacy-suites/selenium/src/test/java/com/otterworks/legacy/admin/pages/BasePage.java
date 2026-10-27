package com.otterworks.legacy.admin.pages;

import java.time.Duration;
import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;

public abstract class BasePage {
  protected final WebDriver driver;
  private final String baseUrl;

  protected BasePage(WebDriver driver) {
    this.driver = driver;
    this.baseUrl = System.getenv().getOrDefault("ADMIN_BASE_URL", "http://localhost:4200");
    this.driver.manage().timeouts().implicitlyWait(Duration.ofSeconds(5));
  }

  protected void open(String path) {
    driver.get(baseUrl + path);
    pause();
  }

  protected String readText(By locator) {
    return driver.findElement(locator).getText().trim();
  }

  protected void enterText(By locator, String value) {
    WebElement element = driver.findElement(locator);
    element.clear();
    element.sendKeys(value);
  }

  protected boolean isPresent(By locator) {
    return !driver.findElements(locator).isEmpty();
  }

  protected void pause() {
    try {
      Thread.sleep(700);
    } catch (InterruptedException exception) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException("Browser wait interrupted", exception);
    }
  }
}
