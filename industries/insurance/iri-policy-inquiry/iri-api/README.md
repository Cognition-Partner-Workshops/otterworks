# Shared IRI API (JDK 17 / Spring Boot 3)

No policy operation is implemented here yet. Health checks Oracle with SELECT 1
FROM dual and returns STATUS/DB UP, or HTTP 503 with STATUS/DB DOWN.
Lifecycle readiness requires both to be UP. Actual inquiry queries must surface
connection failures as 503 using the shared advice.

## Parallel ownership

Each operation session owns **only** its package subtree (main and test), plus its
own operation documentation if needed:

| Operation | Main/test package under app.synthetic.insurance.iri |
| --- | --- |
| summary | summary |
| values | values |
| funds | funds |

Create your controller, repository, mapper, DTOs and tests inside that package;
Spring component scanning discovers them. Do not edit IriApplication, shared,
pom.xml, application.yml, lifecycle.py, lineage, parity tools, Makefile or the skill
in an operation session. Raise shared mapping changes to the coordinating session.
Do not share repository/DTO files between operations. Use constructor injection
of JdbcTemplate; datasource is already wired to ANNUITY_INQ. Throw ApiException
for expected 400/404, DataAccessException becomes 503. correlationId is header-only.

Read ../lineage/LINEAGE.md and the iri-policy-inquiry skill before implementing.
Sign-off is not permission to delete a field or invent business data; unresolved
decisions remain explicitly tracked, including required schema fields.
Use the pinned spec as authority, not a hand-copied DTO schema.

From repo root: make iri-api-test NS=iri (no Oracle), make iri-api-up NS=iri,
make iri-api-down NS=iri. Port is 19080 + crc32(NS)%1000; Oracle is
51521 + the same offset. Set JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64.
Wrapper/settings mirror match legacy-api. No operation session owns frozen captures.
