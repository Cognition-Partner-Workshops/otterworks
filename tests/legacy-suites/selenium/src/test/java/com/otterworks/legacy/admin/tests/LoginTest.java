package com.otterworks.legacy.admin.tests;

import com.otterworks.legacy.admin.pages.LoginPage;
import org.testng.Assert;
import org.testng.annotations.Test;

public final class LoginTest extends AdminTestBase {
  @Test
  public void loginFormShowsEmailField() {
    LoginPage page = new LoginPage(driver);
    page.open();
    Assert.assertTrue(page.hasEmailInput());
  }

  @Test
  public void emptyCredentialsShowValidationMessage() {
    LoginPage page = new LoginPage(driver);
    page.open();
    page.submit();
    Assert.assertTrue(page.errorText().contains("Please enter both email and password."));
  }

  @Test
  public void passwordVisibilityCanBeChanged() {
    LoginPage page = new LoginPage(driver);
    page.open();
    page.enterPassword("DemoPass123!");
    page.togglePasswordVisibility();
    Assert.assertEquals(page.passwordInputType(), "text");
  }
}
