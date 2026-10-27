describe("Settings", () => {
  beforeEach(() => {
    cy.intercept("**/api/v1/**", { statusCode: 200, body: { data: [], total: 0 } });
    cy.intercept("GET", "**/auth/profile", { fixture: "user.json" });
    cy.intercept("GET", "**/api/v1/settings*", { fixture: "settings.json" }).as("settings");
    cy.intercept("PATCH", "**/auth/profile", { fixture: "user.json" }).as("profileUpdate");
  });

  it("updates the profile name", () => {
    cy.visitAsUser("/settings");
    cy.wait("@settings");
    cy.get("#name").clear().type("Casey Taylor");
    cy.contains("button", "Save changes").click();
    cy.wait("@profileUpdate")
      .its("request.body")
      .should("include", { displayName: "Casey Taylor" });
  });
});
