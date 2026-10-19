Feature: Application Navigation
  As a user
  I want to navigate between pages
  So that I can access all Fernwold workspace features

  Scenario: Landing page is accessible
    Given I navigate to "/"
    Then I should see the heading "Every spec, label proof and promo plan, in one place"

  Scenario: Login page is accessible
    Given I navigate to "/login"
    Then I should see the text "Sign in to Fernwold"

  Scenario: Registration page is accessible
    Given I navigate to "/register"
    Then I should see the text "Create your account"

  Scenario: Dashboard page loads or redirects
    Given I navigate to "/dashboard"
    Then I should see the text "Dashboard" or "Sign in to Fernwold"

  Scenario: Specs page loads or redirects
    Given I navigate to "/documents"
    Then I should see the text "Specs & briefs" or "Sign in to Fernwold"

  Scenario: Files page loads or redirects
    Given I navigate to "/files"
    Then I should see the text "Files" or "Sign in to Fernwold"

  Scenario: Search page loads or redirects
    Given I navigate to "/search"
    Then I should see the text "Search" or "Sign in to Fernwold"

  Scenario: Settings page loads or redirects
    Given I navigate to "/settings"
    Then I should see the text "Settings" or "Sign in to Fernwold"

  Scenario: Notifications page loads or redirects
    Given I navigate to "/notifications"
    Then I should see the text "Notification" or "Sign in to Fernwold"

  Scenario: Shared page loads or redirects
    Given I navigate to "/shared"
    Then I should see the text "Shared" or "Sign in to Fernwold"

  Scenario: Trash page loads or redirects
    Given I navigate to "/trash"
    Then I should see the text "Trash" or "Sign in to Fernwold"
