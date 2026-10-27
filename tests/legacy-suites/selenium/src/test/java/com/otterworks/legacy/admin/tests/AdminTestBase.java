package com.otterworks.legacy.admin.tests;

import org.openqa.selenium.Dimension;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.chrome.ChromeOptions;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;

public abstract class AdminTestBase {
  protected WebDriver driver;

  @BeforeMethod
  public void startBrowser() {
    ChromeOptions options = new ChromeOptions();
    options.addArguments("--headless=new", "--no-sandbox", "--disable-dev-shm-usage");
    driver = new ChromeDriver(options);
    driver.manage().window().setSize(new Dimension(1280, 800));
  }

  @AfterMethod(alwaysRun = true)
  public void stopBrowser() {
    if (driver != null) {
      driver.quit();
    }
  }
}
