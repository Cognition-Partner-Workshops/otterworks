Feature: Application Navigation
  As a user
  I want to navigate between pages
  So that I can access all features of Larkbridge Freight

  Scenario: Landing page is accessible
    Given I navigate to "/"
    Then I should see the heading "Larkbridge Freight"

  Scenario: Login page is accessible
    Given I navigate to "/login"
    Then I should see the text "Sign in to track loads and open shipment files"

  Scenario: Registration page is accessible
    Given I navigate to "/register"
    Then I should see the text "Create a shipper account"

  Scenario: Dashboard page loads or redirects
    Given I navigate to "/dashboard"
    Then I should see the text "Overview" or "Sign in to track loads and open shipment files"

  Scenario: Documents page loads or redirects
    Given I navigate to "/documents"
    Then I should see the text "Paperwork" or "Sign in to track loads and open shipment files"

  Scenario: Files page loads or redirects
    Given I navigate to "/files"
    Then I should see the text "Shipment files" or "Sign in to track loads and open shipment files"

  Scenario: Search page loads or redirects
    Given I navigate to "/search"
    Then I should see the text "Search shipments and files" or "Sign in to track loads and open shipment files"

  Scenario: Settings page loads or redirects
    Given I navigate to "/settings"
    Then I should see the text "Settings" or "Sign in to track loads and open shipment files"

  Scenario: Notifications page loads or redirects
    Given I navigate to "/notifications"
    Then I should see the text "Notification" or "Sign in to track loads and open shipment files"

  Scenario: Shared page loads or redirects
    Given I navigate to "/shared"
    Then I should see the text "Shared" or "Sign in to track loads and open shipment files"

  Scenario: Trash page loads or redirects
    Given I navigate to "/trash"
    Then I should see the text "Trash" or "Sign in to track loads and open shipment files"
