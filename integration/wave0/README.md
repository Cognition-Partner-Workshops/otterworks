# Wave 0 shared runtime (tib-d1111)

Java 21 / Boot 3.5.3 / Camel 4.12.0. No routes are converted here.
The four shared modules scan their complete application package, including
`com.halvergate.<module-without-hyphens>.packages.*`. Runtime's
`@PropertySource(classpath*:packages/*/package.yaml)` loads every package YAML
using Spring's resource-pattern resolver, including nested YAML keys. Packages
do not edit application.yaml. Property names must be package-prefixed to avoid
collisions. YAML must contain application properties, not Spring profile documents.

## Local stack

Build with `integration/target/mvnw -f integration/target/pom.xml package` on JDK 21.
`make tibco-up NS=w0` prepares the isolated fixture, as before;
`make tibco-runtime-up NS=w0` builds and starts the four empty modules.
`MODULES=customer-alerts` selects one module (also accepts payments for the
read-only pilot prerequisite). `make tibco-down NS=w0` removes this namespace.
Docker Compose v2 is required. Make's socket group detection supports GNU/Linux
and BSD/macOS stat. macOS execution is **not verified by this Linux checkpoint**.
Do not enable the application profile to satisfy HTTP calls with the unrelated
golden app. No production endpoints or credentials are configured.

The override changes only the four shared services, selecting Dockerfile.runtime
and separate persistent /app/transaction-logs volumes owned by the integration user.
Payments keeps its own pilot wiring, requiring PR #2792 independently.
Artemis and PostgreSQL XA factories are wrapped by Narayana's Boot integration.
The primary DataSource is XA; inject `@Qualifier("autoCommitDataSource")` explicitly
for AUTO_COMMIT activity JDBC. The latter is not enlisted in JTA. JMS uses
CACHE_NONE, exposeListenerSession, persistent sends, one consumer and 100ms
recovery. Global route configuration sets Camel redeliveries to zero.

Packages must preserve source transaction scopes; availability of JTA does not
authorize widening them. Use the `required` policy only as needed.
`TransactionOutcomeLogger.register(requestId)` registers COMMIT/ROLLBACK logging
inside an active transaction; package processors log receive / inserted / published.
`runtime.output-queues.<package>` lists durable ANYCAST output queues. Lists from
all package keys are combined and deduplicated, avoiding cross-package overrides.
These are declared
before Camel starts routes; empty lists connect to nothing. Packages must keep
routes autoStartup(false), verify DB and warm their own Saxon transformers, then
start them after readiness. For literal JMSX headers use the pilot core XA
publisher pattern, not normal JMS which rewrites JMSXGroupID. That publisher
is not copied or activated here.

## Package verification discovery

Run `python -m integration.wave0.discover` or `make tibco-packages`.
It globs `integration/target/*/verification/*.yaml`; no manifests yields JSON
`{"include":[]}` and the explicit diagnostic **no packages selected**. No matches
are inferred from skeletons. CI is additive to tibco-parity.yml, never replaces it.
Each selected package gets an isolated matrix job, starts only its module,
and invokes the unchanged `make tibco-replay NS=ci FLOW=<id>` against the original
frozen corpus for every non-held flow. Differences (including amber) fail CI.
Amber means recorded disagreement, not permission to suppress a difference.
Held-only packages have no replay requirement. No live faults run in this workflow.

Example manifest `fees-billing/verification/fees.yaml` (schema version 1,
all shown fields required, unknown fields rejected):

```yaml
version: 1
package: fees
module: fees-billing
flows:
  - id: fees-billing.fee-posting
    status: matched-required
    evidence:
      - Processes/fees-billing/fee-posting.bwp:14 concrete queue starter
  - id: fees-billing.daily-fee
    status: held
    evidence:
      - Timer without schedule; no producer proven
faults:
  definitions: supplemental.yaml
  lock: sha256.json
```

Package must equal filename stem, module must equal enclosing directory.
IDs must exist in the frozen corpus, belong to the module and occur once globally.
Allowed statuses: matched-required, amber, held. Every flow requires nonempty
evidence (amber records both raw values, held states missing entry evidence).

### Separately locked supplemental fault contract

Both paths above are relative to
`<module>/src/test/resources/packages/<package>/faults/`.
Absolute/path traversal and symlink escapes are rejected. Lock is a JSON map
with exactly the definitions filename and its lowercase SHA-256 hex digest.
Definition YAML:

```yaml
version: 1
flows:
  fees-billing.fee-posting:
    source_sha256: <sha256 of unchanged integration/corpus/fees-billing.fee-posting/flow.json>
    faults:
      broker-kill:
        after_message: 1
        identity_header: requestId
        container_env: REPLAY_BROKER_CONTAINER
```

Only selected IDs and runner fault names broker-kill, consumer-restart, poison,
ordering are accepted. Definitions contain **fault parameters only**, not changed
inputs, expectations, capture or ignore rules. Discovery validates file/schema,
source and lock hashes; the separate parity session validates each fault's actual
runner parameters and deployment identities, then calls unchanged replay_flow
with an in-memory copy of the frozen flow plus the supplemental faults mapping.
Do not mutate/relock the original corpus or claim this checkpoint certifies faults.
No supplemental faults are authored for nonexistent packages here. Four clean
broker kills and durable subscriber restart evidence remain separate requirements.

## Frozen fixture and legacy contracts

- HB.UNDLV is broker-owned DLA: no application consumer. Existing broker.xml sets
  max-delivery-attempts=4 = maxRedelivery 3 + initial delivery, delay=100ms.
  No in-memory Camel redelivery, duplicate-key suppression or synthetic audit
  side effects may be added to make parity pass.
- Durable client ID is halvergate-records; account topic subscriber names are
  records-account-opened, records-address-changed, records-limit-changed,
  records-account-closed. event-fanout remains amber: legacy queue starter vs
  corpus durable-topic records-event-fanout; no new starter is invented.
  Shared client IDs may require a shared physical connection for simultaneous
  durable subscriptions; package readiness must prove actual identities.
- Call-process names resolve by suffix: account-events.* / payments.* /
  statements-documents.* to halvergate.<same suffix>. Bind to
  direct:<module>.<flow>, preserving body and contract headers at call time.
  No explicit input mapping is present in the BW call configuration. Do not
  replace the caller body with a new request, publish a queue pipeline or remove
  the callee's independent starter. Pilot calls remain out of scope.
- Corpus request root is unqualified despite imported namespaced request.xsd.
  Do not introduce schema validation or namespace normalization.
- HTTP POST side effects are **not captured** by the harness (messages/DB/files
  only). Dev literal URLs: notifications http://notification-service:8086/api/notifications,
  billing http://billing-service:8092/api/fees, files http://file-service:8082/api/files,
  screening http://screening:8080/v1/screen (not production v2).
  These hosts are not running HTTP fixtures in the frozen local stack. A package
  requiring real HTTP success must escalate a missing fixture contract, not omit
  the call or claim parity covers HTTP. No HTTP stub semantics are invented here.
- preference-sync and fee-posting POST **before** AUTO_COMMIT insert. Keep that
  order and non-XA DataSource; do not move POST after commit or add idempotence.
  The generic skill's after-commit guidance does not override observed legacy.
- SFTP is replay/integration-local-only on sftp:22, paths upload/in and upload/out;
  override local password via TIBCO_LOCAL_PASSWORD. Do not invent production values.
  Files are captured by the harness; document-store remains amber (corpus files
  vs source HTTP-only). daily-fee/month-end-summary have unknown entry contracts:
  held individually, no invented schedule or queue starter.
