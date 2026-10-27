describe("Starred documents", () => {
  beforeEach(() => {
    cy.intercept("**/api/v1/**", { statusCode: 200, body: { data: [], total: 0 } });
    cy.intercept("GET", "**/auth/profile", { fixture: "user.json" });
    cy.intercept("GET", "**/documents/doc-101", { fixture: "document.json" }).as("document");
  });

  it("shows a saved document", () => {
    cy.visitAsUser("/starred", {
      starredItems: {
        "user-123:doc-101": {
          itemId: "doc-101",
          itemType: "document",
          starredAt: "2025-02-18T08:00:00.000Z",
        },
      },
    });
    cy.wait("@document");
    cy.contains("Quarterly Planning").should("be.visible");
  });
});
