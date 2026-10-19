Feature: Application Navigation
  As a user
  I want to navigate between pages
  So that I can access all features of Pennant Lane

  Scenario: Landing page is accessible
    Given I navigate to "/"
    Then I should see the heading "Pennant Lane"

  Scenario: Login page is accessible
    Given I navigate to "/login"
    Then I should see the text "Sign in with your store account"

  Scenario: Registration page is accessible
    Given I navigate to "/register"
    Then I should see the text "Create your store account"

  Scenario: Dashboard page loads or redirects
    Given I navigate to "/dashboard"
    Then I should see the text "Dashboard" or "Sign in with your store account"

  Scenario: Documents page loads or redirects
    Given I navigate to "/documents"
    Then I should see the text "Documents" or "Sign in with your store account"

  Scenario: Files page loads or redirects
    Given I navigate to "/files"
    Then I should see the text "Files" or "Sign in with your store account"

  Scenario: Search page loads or redirects
    Given I navigate to "/search"
    Then I should see the text "Search" or "Sign in with your store account"

  Scenario: Settings page loads or redirects
    Given I navigate to "/settings"
    Then I should see the text "Settings" or "Sign in with your store account"

  Scenario: Notifications page loads or redirects
    Given I navigate to "/notifications"
    Then I should see the text "Notification" or "Sign in with your store account"

  Scenario: Shared page loads or redirects
    Given I navigate to "/shared"
    Then I should see the text "Shared" or "Sign in with your store account"

  Scenario: Trash page loads or redirects
    Given I navigate to "/trash"
    Then I should see the text "Trash" or "Sign in with your store account"
