# Synthetic annuity policy inquiry

The legacy policy inquiry API serves a synthetic annuity book from Oracle's
`ANNUITY_INQ` schema. Its three read operations are summary, values, and funds
under `/pinq/v1/`; responses are flat JSON objects. `/pinq/v1/contracts`
enumerates the book.

Start the database with `make insurance-up NS=iri`, then start the API with
`make iri-legacy-up NS=iri`. Health is available at
`http://127.0.0.1:18765/health` for that namespace; startup prints the API URL
for other namespaces. Stop the API with `make iri-legacy-down NS=iri`.
Run DB-independent API tests with `make iri-legacy-test`.

The pinned IRI Policy Inquiry v1.1.5 specification and its source attribution
are in `vendor/iri-policy-inquiry-v1.1.5/`.
