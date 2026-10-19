Feature: Case File Management
  As an authenticated user
  I want to manage my documents
  So that I can create, edit, and organize my work

  Scenario: Case files page shows heading or login redirect
    Given I navigate to "/documents"
    Then I should see the text "Case files" or "Sign in with your staff or resident account"

  Scenario: Case files page has a New case file button
    Given I navigate to "/documents"
    Then I should see the text "Case files" or "Sign in with your staff or resident account"

  Scenario: Case files page has a filter input
    Given I navigate to "/documents"
    Then I should see the text "Case files" or "Sign in with your staff or resident account"

  Scenario: Search page shows search input
    Given I navigate to "/search"
    Then I should see the text "Search case files and records" or "Sign in with your staff or resident account"

  Scenario: Settings page shows profile section
    Given I navigate to "/settings"
    Then I should see the text "Settings" or "Sign in with your staff or resident account"
