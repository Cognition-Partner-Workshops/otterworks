# Exit plan and assessment rules

## Evidence and inventory

As of 2026-11-10. The inclusive 90-day DBQL observation window is 2026-08-12 through
2026-11-09. Join ObjectUsage to QryLog by QueryID; count READ usage rows (not
result rows). No usage of any kind marks an SFX TablesV object dead. DBC objects
are catalog replacements, not dead estate. Reads occurring only on the initial
setup date are separately flagged, not retired. This is historical observation,
not proof that an object is safe to delete: require an owner sign-off first.

Spark uses a separate inclusive 90-day observation window ending on the newest
packaged eventlog's application-start date: currently 2026-08-13 through
2026-11-10. Derive the start by subtracting 89 days from that date; do not shift
logs or substitute the local run for packaged history. With no applications,
the Spark window is null and run counts are zero.

DDL table/view statements are individually inventoried; macros and procedures
are inventoried from their own source files rather than double-counting TablesV.
DBC catalog rows have zero source LOC. LOC excludes blank and SQL/XML comment
lines; XML LOC is the serialized individual mapping/session/worklet/workflow
element, excluding shared definitions and duplicated mappings in workflow exports.
Control files and BTEQ are whole-file artifacts. The daily chain is orchestration
context, not a separate requested artifact kind. No estate source is changed.
The checked-out branch actually contains 25 BTEQ scripts and 22 FastLoad files,
not the previously estimated 26 and 24; inventory follows files, not estimates.
XML definitions without OWNERNAME resolve against a unique DDL object basename;
ambiguous or missing matches stop generation rather than inventing a schema.

Complexity: high for >=100 LOC, >=4 distinct construct labels, or Sequence,
Unconnected, or Use First Value semantics; medium for >=35 LOC or any construct;
otherwise low. SQL labels detect .IF, .GOTO, .EXPORT, QUALIFY, MERGE, VOLATILE,
SET TABLE and CURSOR. Mapping labels include transformation types, transformation
count and lookup policy. High-risk planted SFX classes are attached by object or
artifact file; risk is also high for high complexity, medium for medium complexity.
These are triage scores, not conversion estimates.

## Target decisions

- Dead SFX objects retire; DBC objects retire with the distinct reason
  `replaced by SNOWFLAKE.ACCOUNT_USAGE`.
- Transitively retire artifacts whose only data downstream is dead, with reason
  `feeds only dead objects`. Ignore orchestration containment and observed setup
  consumers for this decision; sessions follow their associated mapping. Staging
  tables also depend on their same-named core destination (STG_ prefix removed),
  even when a disabled/unwired load has no parsed edge. Keep these dependent
  retirements distinct from the six DBQL-dead objects and from licence remaining.
- FastLoad/TPT become COPY-oriented Snowflake Scripting procedures under
  RAW_<AREA>.LOAD_<AREA>; multiple control files share an area landing entrypoint.
- Staging and core tables become dbt staging/core models. SQL-compatible mappings
  and sessions become dbt models. State-bearing Sequence, unconnected lookups and
  Use First Value mappings become Snowpark pending semantic equivalence tests.
- SPL procedures, macros, control-flow/export BTEQ become Snowflake Scripting.
  Other BTEQ core loads become dbt models. Workflow/worklet targets are Task DAGs.
- Views become COMPAT compatibility views, including those not yet read by a
  registered consumer (conservative interface preservation).
- Targets are concrete proposed deployment names, not provisioned objects.
  Session models represent orchestration wrappers; consolidate with mapping
  targets during implementation, not by removing inventory evidence.

## Waves and dependencies

1. Retire approved dead/catalog objects; land feeds and stage data.
2. Users, documents and audit core, starting with lower-risk paths.
3. Billing/GL finance core, macros/procedures and billing orchestration.
4. Compatibility views, consumer repointing (including hidden principals), remaining
   workflow Task DAGs and final Teradata/PowerCenter decommission.

These are initial floors. Parsed data dependencies monotonically raise a
dependent's wave to its prerequisite's wave until stable. Cycles execute in the
same wave and need implementation-time ordering; waves do not imply an executable
task schedule. Retired nodes are excluded from active dependency ordering (their
retirement needs owner approval rather than materialization). Session containment
depends on mapping completion; DAG containment depends on its sessions/worklets.
Consumers are Wave 4 gates, separate from artifact inventory and object counts.

## Ownership and consumer discovery

For each object count DBQL reads by registered service accounts directly and
through downstream views/macros/procedures, choose the most frequent reader's
registry team (ties lexicographic by account). Without such evidence assign
`@otterworks/data-platform`, owner_source `proposed`. This is a proposal, not an
assertion of organizational accountability. Hidden consumers have unknown owner
and high risk; confirm ownership before cutover. Registered accounts without
DBQL evidence remain in the plan. Utility/ETL principals remain scan evidence,
not user-facing consumers. Registered teams are copied without alteration.
Load artifacts inherit readership of their parsed target tables; sessions inherit
the targets of their associated mapping. No load path is followed when attributing
a table's own readership: only downstream serving objects are included.

Scan every DBQL READ principal against tracked repository text excluding DBQL,
tests, and this generated assessment. Record all hit paths plus the warehouse/ETL
subset; “not in any code” means no hit in that repository scan, not absence of a
workstation/notebook outside version control. Client and application evidence is
retained for the hidden readers. A registry-only or consumer-directory-only hit
must not be confused with presence in warehouse/ETL load code.

## Known parse limits and follow-up gates

- Static SQL FROM/JOIN and INSERT/MERGE/UPDATE references only: no dynamic SQL,
  unqualified-name resolution, CTE expansion, CALL/EXEC binding or column lineage.
- Mapping SOURCE/TARGET INSTANCE definitions are parsed; lookup cache tables and
  expression-embedded SQL need manual dependency review. SQL references outside
  the inventoried file types and daily-chain shell sequencing are not DAG edges.
- Source feed labels in mappings are flat-file definition names; control files
  retain landing path templates. Reconcile equivalent feed aliases during landing.
- DBQL READ attribution on scripts/mappings is not inferable from object usage:
  their direct read count is zero; referenced table/view counts are authoritative.
- Setup-only flag uses the initial observation date, not an explicit DBQL setup
  marker. Validate those reads before any subsequent retirement decision.
- Spark is read from the current working tree under etl/spark; Teradata,
  PowerCenter, registry and DBQL remain pinned to BEFORE_STATE. Inventory is the
  union of jobs.txt and jobs/registry filenames. Registry status/classification
  text is not decision evidence. Python AST and static Scala helper calls resolve
  landing/register inputs, save/save_partition outputs and JDBC targets using
  common/runtime.py and BatchSupport semantics. Landing paths reuse matching
  FastLoad/TPT feed nodes; JDBC outputs absent from the pinned DDL are external
  table nodes, not invented legacy inventory. Literal lake reads link producers
  to consumers. Dynamic paths, indirect helper aliases and arbitrary custom
  readers/writers require manual review; this is not a full language interpreter.
- Spark LOC and complexity use the same scoring as other artifacts, with udf,
  rdd, window, graph, binary, stateful and jdbc labels. Relational jobs target
  dbt; UDF/RDD/graph/binary/stateful jobs target Snowpark. Retire jobs with a
  disabled/missing cron OR zero in-window runs only when no output reader was
  found. Compaction retires as `replaced by Snowflake storage management`.
  Floors are billing wave 3, other Spark wave 2, retire wave 1; active dependency
  edges raise floors. Ownership uses output readership, never input readership.
- Spark listener logs in history/eventlogs are decompressed with eventlog.py and
  summarized with compute_baseline.py; baseline.json must agree. Count application
  starts in the Spark observation window defined above; last run and total
  executor-hours retain all packaged history, with in-window hours reported
  separately. The July 15 legacy-report run is outside that window.
  The November 19 local run is not substituted for historical evidence. Its binary
  extraction import failure is a finding, not a source fix. Output-reader scans
  use hidden-consumer exclusions and exclude etl/spark except analyzed job code.
  Readers must be another Spark job, a pinned registered consumer, or
  service/client/notebook code. Exclude warehouse/dbt, warehouse/snowflake,
  warehouse/parity, warehouse/snowpark, warehouse/pipeline, migration/,
  etl/airflow, docs/ and *.md from readers. Preserve matching excluded paths and
  relations as non_reader_mentions with the exclusion reason. Text mentions in
  replacement models or descriptions are not evidence of legacy consumption.
- Every retirement carries usage/run evidence. Teradata evidence joins the full
  QryLog/ObjectUsage history, preserves usage counts in-window, last read/write
  ever and the last five accesses with QueryIDs/principals. Dependent retirements
  also name the dead objects they feed. Non-retired objects last read strictly
  before September 10 (>60 days before November 9) are in the stale owner-review
  list, not auto-retired. Null last reads do not assert an old read date.
- Mermaid output uses sanitized stable IDs and quoted labels. Rendering is not
  performed by the offline validator; syntax and node completeness are checked.
- No live Snowflake assessment/load, parity run, migration status transition or
  decommission has been attempted. Later acts use MIGRATION_CONTROL status to
  drive licence counters to zero. Annual licence cost is the configured contract
  annual cost, not the sum of overlapping option list prices.
