Feature: Landing Page
  As a visitor
  I want to see the Careotter landing page
  So that I can learn about the product and sign up

  Scenario: Visitor sees the hero section
    Given I am on the landing page
    Then I should see the heading "Careotter"
    And I should see the text "Patient records management for modern medical practices"

  Scenario: Visitor sees navigation CTAs
    Given I am on the landing page
    Then I should see a link "Sign In"
    And I should see a link "Create Account"

  Scenario: Visitor sees all feature cards
    Given I am on the landing page
    Then I should see the text "Patient Records"
    And I should see the text "Chart Editing"
    And I should see the text "Care Team Collaboration"
    And I should see the text "Powerful Search"
    And I should see the text "HIPAA-Ready Sharing"
    And I should see the text "Instant Notifications"

  Scenario: Sign In link navigates to login
    Given I am on the landing page
    When I click the link "Sign In"
    Then the URL should contain "/login"

  Scenario: Create Account link navigates to register
    Given I am on the landing page
    When I click the link "Create Account"
    Then the URL should contain "/register"

  Scenario: Footer is visible
    Given I am on the landing page
    Then I should see the text "Patient records management for doctor offices"
