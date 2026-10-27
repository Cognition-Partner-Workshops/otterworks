Cypress.Commands.add("visitAsUser", (path, options = {}) => {
  cy.visit(path, {
    onBeforeLoad(window) {
      window.localStorage.setItem(
        "otter_access_token",
        "header.eyJzdWIiOiJ1c2VyLTEyMyJ9.sig",
      );
      window.localStorage.setItem("otter_refresh_token", "refresh-token");
      if (options.starredItems) {
        window.localStorage.setItem(
          "otter_starred_items",
          JSON.stringify(options.starredItems),
        );
      }
    },
  });
});
