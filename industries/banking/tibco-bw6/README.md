# Halvergate integration sources

The fictional retail-bank estate lives in [`integration/legacy-bw6/`](../../../integration/legacy-bw6/).
Its 24 BW6-style processes span payments, account events, fees and billing,
statements and documents, and customer alerts. No licensed BW6 runtime is included.

[`reference/`](../../../integration/legacy-bw6/reference/) executes project-owned
XSLT with Saxon-HE and Java activities on Java 21. It freezes transformation
outputs into [`integration/corpus/`](../../../integration/corpus/), with explicit
reason-required recording and source hashes. Transport, database and file
expectations are derived from the declared process configuration; this recorder
does not execute BW6, XA transactions or broker delivery semantics.

[`integration/harness/`](../../../integration/harness/) verifies the corpus lock,
replays messages and SFTP inputs, and compares messages, rows and files.
[`integration/target/`](../../../integration/target/) contains five buildable
Spring Boot 3 / Camel 4 skeletons with no routes. The initial parity baseline is
therefore red for all 24 flows. [`docker-compose.tibco.yml`](../../../docker-compose.tibco.yml)
isolates Artemis, PostgreSQL and SFTP by `NS` through the `tibco-*` Make targets.
The runner's Docker socket mount is exclusively for local fault injection and
must not be used in a deployed service. Its pinned SFTP host key is bootstrapped
from the isolated local fixture, not a production trust authority.

The [`complexity register`](../../../demos/app/complexity-manifest.json) identifies
source-level behavior and decision stages. Month-end channel rounding remains
an unresolved business decision; matching the frozen channel-specific behavior
does not approve a new fee policy. [`integration/sessions/`](../../../integration/sessions/)
reserves space for migration session data.
