describe("Document search", () => {
  beforeEach(() => {
    cy.intercept("**/api/v1/**", { statusCode: 200, body: { data: [], total: 0 } });
    cy.intercept("GET", "**/auth/profile", { fixture: "user.json" });
    cy.intercept("GET", "**/api/v1/search*", { fixture: "search-results.json" }).as("search");
  });

  it("finds a document by title", () => {
    cy.visitAsUser("/search?q=quarterly");
    cy.wait("@search");
    cy.contains("Quarterly Planning").should("be.visible");
    cy.get('input[placeholder="Search files, documents, and folders..."]')
      .should("have.value", "quarterly");
  });
});
