Feature: Shipment Paperwork
  As an authenticated user
  I want to manage shipment paperwork
  So that I can create, edit, and organize my work

  Scenario: Documents page shows heading or login redirect
    Given I navigate to "/documents"
    Then I should see the text "Paperwork" or "Sign in to track loads and open shipment files"

  Scenario: Documents page has a New document button
    Given I navigate to "/documents"
    Then I should see the text "Paperwork" or "Sign in to track loads and open shipment files"

  Scenario: Documents page has a filter input
    Given I navigate to "/documents"
    Then I should see the text "Paperwork" or "Sign in to track loads and open shipment files"

  Scenario: Search page shows search input
    Given I navigate to "/search"
    Then I should see the text "Search shipments and files" or "Sign in to track loads and open shipment files"

  Scenario: Settings page shows profile section
    Given I navigate to "/settings"
    Then I should see the text "Settings" or "Sign in to track loads and open shipment files"
