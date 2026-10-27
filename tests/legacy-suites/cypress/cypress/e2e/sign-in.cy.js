describe("Sign in", () => {
  beforeEach(() => {
    cy.intercept("**/api/v1/**", { statusCode: 200, body: { data: [], total: 0 } });
    cy.intercept("POST", "**/auth/login", { fixture: "auth-tokens.json" }).as("login");
    cy.intercept("GET", "**/auth/profile", { fixture: "user.json" }).as("profile");
  });

  it("opens the dashboard with a valid account", () => {
    cy.visit("/login");
    cy.get("#email").type("alex.morgan@example.test");
    cy.get("#password").type("DemoPass123!");
    cy.contains("button", "Sign in").click();
    cy.wait("@login");
    cy.wait("@profile");
    cy.location("pathname").should("eq", "/dashboard");
    cy.contains("Alex Morgan").should("be.visible");
  });

  it("requires an email address", () => {
    cy.visit("/login");
    cy.get("#password").type("DemoPass123!");
    cy.contains("button", "Sign in").click();
    cy.contains("Please enter a valid email").should("be.visible");
  });
});
