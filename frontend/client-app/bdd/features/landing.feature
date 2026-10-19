Feature: Landing Page
  As a resident
  I want to see the Brindlemoor DRS landing page
  So that I can learn about department services

  # AC-01 / BDD-01
  Scenario: Visitor sees the department hero with the statehouse logo
    Given I am on the landing page
    Then I should see the heading "Brindlemoor DRS"
    And I should see the Brindlemoor DRS logo
    And I should see the text "One office for case files, permits, benefits and public records. Residents apply and check status online, and caseworkers keep every file, note and decision in the same record. Serving the state since 1962."

  Scenario: Visitor sees navigation CTAs
    Given I am on the landing page
    Then I should see a link "Sign In"
    And I should see a link "Create Account"

  # AC-03 / BDD-07
  Scenario: Visitor sees the full corporate identity sections
    Given I am on the landing page
    Then I should see the text "About the department"
    And I should see the text "Leadership"
    And I should see the text "Divisions"
    And I should see the text "Services"
    And I should see the text "News and notices"
    And I should see the text "Careers"

  Scenario: Sign In link navigates to login
    Given I am on the landing page
    When I click the link "Sign In"
    Then the URL should contain "/login"

  Scenario: Create Account link navigates to register
    Given I am on the landing page
    When I click the link "Create Account"
    Then the URL should contain "/register"

  # AC-02c / BDD-06
  Scenario: Corporate footer is visible with legal links
    Given I am on the landing page
    Then I should see the text "© State of Brindlemoor"
    And I should see a link "Terms"
    And I should see a link "Privacy"

  # AC-02c / BDD-06
  Scenario: Terms and Privacy static pages are reachable
    Given I navigate to "/terms"
    Then I should see the heading "Terms of Service"
    Given I navigate to "/privacy"
    Then I should see the heading "Privacy Policy"
