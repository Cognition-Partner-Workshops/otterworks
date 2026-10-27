package com.otterworks.legacy.admin.pages;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;

public final class LoginPage extends BasePage {
  private final By emailInput = By.xpath("//input[@type='email']");
  private final By passwordInput = By.xpath("//input[@name='password']");
  private final By submitButton = By.xpath("//button[contains(@class,'login-btn')]");
  private final By errorMessage = By.cssSelector(".error-message");
  private final By passwordToggle = By.xpath("//button[@type='button']");

  public LoginPage(WebDriver driver) {
    super(driver);
  }

  public void open() {
    open("/login");
  }

  public boolean hasEmailInput() {
    return isPresent(emailInput);
  }

  public void enterEmail(String value) {
    enterText(emailInput, value);
  }

  public void enterPassword(String value) {
    enterText(passwordInput, value);
  }

  public void submit() {
    driver.findElement(submitButton).click();
    pause();
  }

  public String errorText() {
    return readText(errorMessage);
  }

  public void togglePasswordVisibility() {
    driver.findElement(passwordToggle).click();
  }

  public String passwordInputType() {
    return driver.findElement(passwordInput).getAttribute("type");
  }
}
