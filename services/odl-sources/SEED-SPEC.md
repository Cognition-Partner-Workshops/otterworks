# ODL source estate

The `odl` section of `demos/app/complexity-manifest.json` is independent of the
unchanged top-level MIG-01..07 register. This document names the eight ODL data
failure classes; application generators and loaders use ordinary source names.

## Reproducibility and sizes

One generator (`odl_sources/generate.py`) supplies all engines. No current time,
random UUIDs, locale-dependent formatting or database-generated identifiers are
used in row data. `records(Settings(...))` streams canonical ASCII JSON lines;
the same settings yield byte-identical rows. Operational passwords and database
internal pages are not part of that byte-level contract.

| Variable | Default |
| --- | ---: |
| ODL_SEED | 1795112287 |
| ODL_DB2_CUSTOMERS | 50000 |
| ODL_DB2_HISTORY | 400000 |
| ODL_ORACLE_ACCOUNTS | 40000 |
| ODL_PG_CONTACTS | 30000 |
| ODL_DUP_RATE | 0.02 |

Oracle has four products; CRM has two service cases and one subscription snapshot
per contact. Counts must be nonnegative; history requires customers. The rate
must be in [0, 0.25]. A configuration fingerprint avoids reloading complete
sources. A changed configuration replaces only these source-owned tables.

Canonical people overlap by natural name/address, not an exported shared key.
Db2 uses `CHAR(10)` customer numbers, Oracle numeric account IDs, CRM UUIDs. Let
N be the minimum of the three customer/account/contact sizes and K=floor(N*rate).
The first K people exist in Db2 and Oracle with different names **and** addresses,
and are absent from CRM. CRM starts at person K. Thus the default unmatched cohort
is 600/30000 (2%); remaining overlapping people share natural attributes. There
are also ordinary source-exclusive people because total source sizes differ.
No crosswalk or canonical person ID is loaded into any database.

## Failure register and examples

- **ODL-01 padded keys:** all 50000 Db2 keys have two trailing ASCII blanks;
  `HEX(CUST_NO)` for `C0000001` ends `2020`. History uses exactly the same keys.
- **ODL-02 sentinel dates/packed date:** person indices divisible by 100 have
  DATE `0001-01-01` and DECIMAL(8,0) `10101` (eight-digit form `00010101`), 500
  rows. Other rows carry ordinary dates and their YYYYMMDD decimal values.
  Db2 DECIMAL is physically packed decimal; this is not a text date column.
- **ODL-03 binary-double money:** CRM `credit` is DOUBLE PRECISION. Every 50th
  contact has `0.1+0.2`, rendered `0.30000000000000004`, exactly 600 examples.
  Oracle balances remain exact NUMBER(15,2), as requested.
- **ODL-04 timezone shift:** Oracle DATEs are New York wall-clock values without
  stored offsets. All 40000 have a time component; the first four bracket the
  2024 spring transition and repeat the autumn 01:xx hour. Those four have IDs
  7000000, 7000017, 7000034, 7000051. Treating them as UTC moves real instants by
  four/five hours; the autumn values cannot be uniquely disambiguated without a
  source policy. The loader session and server TZ are America/New_York.
- **ODL-05 codepage:** every 100th Db2 name is accented José García encoded as
  raw cp037 bytes in FOR BIT DATA, following the migration fixture's byte-level
  technique. There are 500 rows; decoding those bytes naively as UTF-8 produces
  replacement characters. Ordinary names are UTF-8 bytes. The supplied query
  returns raw HEX, so CLP/client conversion cannot silently conceal the issue.
- **ODL-06 billing rename:** the real existing billing mapping reads SQL
  `billing_svc.subscriptions.status` and returns REST `subscription_status`.
  `crm.subscription_snapshots` holds 30000 ordinary `status='active'` inputs
  to demonstrate that source shape. It is a reference snapshot, **not** a claim
  that core deploys billing-service, or a change to its data/API. Tests check the
  actual repository/REST mapping. No billing-service files are modified.
- **ODL-07 missing index:** CRM cases have a PK only on case_id; contact_id has
  no index (PostgreSQL does not auto-index referencing FK columns). There are
  60000 affected cases and zero contact_id indexes. Use EXPLAIN on
  `SELECT * FROM crm.service_cases WHERE contact_id=<an existing UUID>`.
- **ODL-08 unmatched duplicates:** the first 600 people in Db2/Oracle conflict
  in both name and address, have different physical identifiers and no shared
  key or CRM record. Oracle IDs are 7000000 through 7010183, step 17. Pair their
  position with ordered Db2 `C0000001` through `C0000600` for verification only;
  this positional relationship is not an application crosswalk.

Manifest expected counts are for defaults. At other sizes, ODL-01=D,
ODL-02/05=ceil(D/100), ODL-03=ceil(P/50), ODL-04=min(O,4),
ODL-06=P, ODL-07=0 indexes with 2P affected rows, ODL-08=floor(min(D,O,P)*rate).

## Deployment and cleanup

Prerequisites: AWS/EKS admin access, aws/kubectl/helm/terraform/jq/docker and
Python 3 with PyYAML. Application credentials are read directly from the existing
dashboard Secret, never printed. Source passwords are generated once per tenant
and referenced through Secrets. Every created tenant resource is labeled
`run_token=odl-1795112287`; Helm's post-renderer labels core chart pod templates.
Before creating resources, the wrapper registers a dashboard-shaped tenant
record through the control-table helpers, with the run token and a ten-year
expiry matching `--ttl never`. It refuses to overwrite another run's record.
Successful deployment marks the record active; failure marks it error. The
shared reaper configuration is unchanged.

`teardown-tenant.sh --keep-db` retains the control record so the orphan database
sweep still recognizes the database. A missing namespace alone does not expire
a control record: normal expiry/pin rules still apply (ODL records have a
ten-year expiry). Dashboard check-in may recreate an unowned `free` record;
registration can adopt that record but never one with another run token, and
does not overwrite an existing pin.

Db2 in emptyDir mode and Oracle opt into tenant suspension with
`otterworks.io/scale-with-tenant: "true"`. `tenant-scale.sh`, idle suspension and
the dashboard wake runner scale these StatefulSets along with Deployments;
unlabeled StatefulSets are untouched. The scanner also counts opted-in
StatefulSets. Their refresh CronJobs use the same opt-in and are paused while
down, then resumed on wake. emptyDir data is lost on suspension; the ordinary
minute-scheduled refresh Jobs reload both Db2 and Oracle from the same seed
after they are ready. PostgreSQL remains on RDS and retains its CRM tables.
Database readiness can precede source loading; wait for refresh completion and
verify counts before starting a demo.

The shared reaper and dashboard wake use the platform runner image's bundled
checkout unless a tenant branch is explicitly supplied. Deploying source charts
or using this branch's scaler does not update those shared components: deploying
the new runner and the chart's `statefulsets/scale` RBAC permission is required
for automatic suspension/wake to use this code.

Build from the repository root:

```sh
docker build -f services/odl-sources/Dockerfile -t "$REGISTRY/otterworks-odl/odl-seed:odl-1795112287" .
docker push "$REGISTRY/otterworks-odl/odl-seed:odl-1795112287"
scripts/odl/deploy-odl.sh odltmp --mode before
# after additionally installs services/operational-data-layer/deploy if present
```

Oracle uses upstream linux/amd64 digest
`sha256:366fe85702d764d81a0272b72e94e629290c27aa72a47825fcc45701a0633dac`,
mirrored unchanged into the existing Terraform-managed `otterworks-odl/oracle-free`
repository. The seed image contains the generator, existing seed script, thin
python-oracledb, psycopg, and kubectl for namespace-scoped Db2 CLP execution.
Set ODL_SEED_IMAGE to an immutable seed-image digest for a pinned deployment.

Db2 and Oracle use disk-backed **emptyDir**, never PVC/EBS. The migration chart's
default remains static-PV storage. Db2 also keeps its shared seed workspace in
emptyDir. Initial source Jobs run concurrently with each other and core services;
completed source fingerprints make subsequent checks cheap. Once initial loads
finish, namespace CronJobs check each minute and rebuild Db2/Oracle after pod
replacement. Incomplete loads never record their fingerprint. Do not run
multiple deployment wrappers concurrently for the same tenant.

Use `scripts/teardown-tenant.sh ID` with DB_PASSWORD supplied in the environment
(read it from the same dashboard Secret without echoing). It drops the entire
tenant database, including crm, after deleting the namespace. No shared RDS,
monitoring or ingress infrastructure is destroyed. Teardown also removes this
run's tenant control record and checkout lock, without changing other records.
A non-expiring tenant is
still eligible for platform idle suspension; this wrapper does not pin it in
the dashboard control plane.

Tests:
```sh
python -m unittest discover -s services/odl-sources/tests -v
PYTHONPATH=migration/source python -m unittest seed.test_seed seed.test_oracle_seed -v
uv run --project migration/job --extra dev pytest migration/job/tests
```
