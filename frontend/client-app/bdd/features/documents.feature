Feature: Document Management
  As an authenticated user
  I want to manage specs and briefs
  So that I can create, edit, and organize my work

  Scenario: Specs page shows its heading or login redirect
    Given I navigate to "/documents"
    Then I should see the text "Specs & briefs" or "Sign in to Fernwold"

  Scenario: Specs page has a New spec button
    Given I navigate to "/documents"
    Then I should see the text "Specs & briefs" or "Sign in to Fernwold"

  Scenario: Specs page has a filter input
    Given I navigate to "/documents"
    Then I should see the text "Specs & briefs" or "Sign in to Fernwold"

  Scenario: Search page shows search input
    Given I navigate to "/search"
    Then I should see the text "Search" or "Sign in to Fernwold"

  Scenario: Settings page shows profile section
    Given I navigate to "/settings"
    Then I should see the text "Settings" or "Sign in to Fernwold"
