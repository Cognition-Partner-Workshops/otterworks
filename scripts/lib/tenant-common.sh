#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# OtterWorks multi-tenant demo — shared library
#
# Sourced by deploy-tenant.sh / teardown-tenant.sh / tenant-platform-baseline.sh.
# Holds the naming rules, Terraform-output loading and per-service Helm wiring
# that turn the golden app (see scripts/deploy-dev.sh) into a per-tenant deploy
# in namespace otterworks-<ATTENDEE_ID>.
#
# Design (see docs/MULTI-TENANT-DEMO-PLAN.md):
#   - namespace-per-tenant is the isolation boundary
#   - stateful backends are SHARED physically, isolated LOGICALLY:
#       * per-tenant in-cluster Redis      -> isolates chaos flags / sessions / collab
#       * per-tenant in-cluster MeiliSearch-> isolates search indexes
#       * per-tenant RDS database          -> isolates all Postgres-backed services
#       * shared S3 bucket / DynamoDB tables (dev) reused via shared IRSA roles
#   - frontends go on the SHARED ingress (ClusterIP), not one ELB per tenant
# ------------------------------------------------------------------------------

# Colors / logging ------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[tenant]${NC} $*"; }
warn() { echo -e "${YELLOW}[tenant]${NC} $*"; }
err()  { echo -e "${RED}[tenant]${NC} $*" >&2; }

# Shared constants ------------------------------------------------------------
AWS_REGION="${AWS_REGION:-us-east-1}"
EKS_CLUSTER="${EKS_CLUSTER:-otterworks-dev}"
ECR_PREFIX="otterworks/"
SYSTEM_NAMESPACE="otterworks-system"   # holds the reaper CronJob + RBAC
INGRESS_NAMESPACE="ingress-nginx"

BACKEND_SERVICES=(
  api-gateway auth-service file-service document-service collab-service
  notification-service search-service analytics-service admin-service
  audit-service report-service
)
FRONTEND_SERVICES=(web-app admin-dashboard)
ALL_SERVICES=("${BACKEND_SERVICES[@]}" "${FRONTEND_SERVICES[@]}")

# Service profiles. A full tenant is ~1.5 vCPU / 3.5GiB of requests, which does
# not multiply to 100 tenants affordably -- but few labs exercise all 13
# services. "core" is the subset a browser session actually touches (~0.5 vCPU).
#
# "full" remains the default: "core" deliberately omits admin-service, whose
# planted crash-loop bug is the subject of the bug-hunt labs, so switching the
# default would silently break them. Opt in with --profile core when a lab is
# known not to need the whole estate.
PROFILE_CORE_SERVICES=(api-gateway auth-service file-service document-service web-app)

# Echo the service list for a profile.
profile_services() {
  case "$1" in
    core) printf '%s\n' "${PROFILE_CORE_SERVICES[@]}" ;;
    full) printf '%s\n' "${ALL_SERVICES[@]}" ;;
    *)    err "unknown profile '$1' (expected core or full)"; return 1 ;;
  esac
}

# The gateway proxies each route to http://<service>:<containerPort>, so every
# backend Service must be exposed on its container port (mirrors deploy-dev.sh).
declare -A CONTAINER_PORT=(
  [api-gateway]=8080 [auth-service]=8081 [file-service]=8082 [document-service]=8083
  [collab-service]=8084 [notification-service]=8086 [search-service]=8087
  [analytics-service]=8088 [admin-service]=8089 [audit-service]=8090 [report-service]=8091
)
JVM_SERVICES=" auth-service report-service notification-service analytics-service "

# Naming ----------------------------------------------------------------------
# Namespace must be RFC-1123 (lowercase alnum + '-'); DB name uses '_'.
#
# Must match sanitizeId() in demo-platform/dashboard/lib/util.ts exactly, down
# to the collapsing and the 40-character cut: the dashboard creates the tenant
# under its own version of this id, and a tag or namespace derived from a
# different one points at nothing.
sanitize_id() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' |
    sed 's/[^a-z0-9-]/-/g; s/-\{2,\}/-/g; s/^-*//; s/-*$//' |
    cut -c1-40 | sed 's/-*$//'
}
tenant_namespace() { printf 'otterworks-%s' "$(sanitize_id "$1")"; }

# Git branch -> the Docker tag CI publishes that branch's images under. Docker
# tags allow [a-zA-Z0-9._-] only, so `feature/x` cannot be used verbatim.
branch_tag_slug() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9._-]/-/g'
}

# The tag a tenant's own build is published under. Keyed by tenant id, not by
# branch: several repositories (this one and its forks) push to one registry and
# would otherwise both claim `branch-demo-x`, each serving the other's build.
# Tenant ids are already namespaced per repository by TENANT_PREFIX, so keying
# on them makes the tag say exactly which environment it belongs to. CI and
# deploy-tenant.sh must agree exactly or a tenant silently falls back to the
# golden image, so both call this.
tenant_image_tag() { printf 'tenant-%s' "$(sanitize_id "$1")"; }

# Tenant id for a branch: `workshop-derek` and `demo-derek` both own tenant
# `derek`. The dashboard rejects a redeploy whose branch does not match the one
# the tenant was checked out from, so the collision cannot silently hijack.
#
# TENANT_PREFIX namespaces a whole repository's environments: a fork sets it so
# that its `demo-derek` is tenant `<prefix>-derek` with its own namespace,
# database and hostname, rather than redeploying the upstream repo's `derek`
# out from under whoever is using it. Unset upstream, where the bare id is the
# one people already know.
branch_tenant_id() {
  local id
  id="$(printf '%s' "$1" | sed -E 's#^(workshop|demo)[-/]##')"
  sanitize_id "${TENANT_PREFIX:+${TENANT_PREFIX}-}${id}"
}
tenant_db_name()   { printf 'otterworks_%s' "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/_/g; s/^_*//; s/_*$//')"; }

require_bins() {
  for bin in "$@"; do
    command -v "$bin" >/dev/null 2>&1 || { err "$bin not found"; exit 1; }
  done
}

# Load shared application-infra Terraform outputs (RDS/Redis/S3/DynamoDB/SNS/SQS
# and the per-service IRSA role ARNs). Same source of truth as deploy-dev.sh.
load_infra_outputs() {
  local d="${REPO_ROOT}/infrastructure/terraform"
  terraform -chdir="$d" init -input=false >/dev/null 2>&1 || true
  local rds; rds="$(terraform -chdir="$d" output -raw rds_endpoint 2>/dev/null || echo "")"
  RDS_HOST="${rds%%:*}"; RDS_PORT="${rds##*:}"
  [ "$RDS_PORT" = "$rds" ] && RDS_PORT=5432 || true
  S3_FILE_BUCKET="$(terraform -chdir="$d" output -raw s3_file_bucket 2>/dev/null || echo "")"
  S3_AUDIT_BUCKET="$(terraform -chdir="$d" output -raw s3_audit_archive_bucket 2>/dev/null || echo "")"
  DDB_FILE_META="$(terraform -chdir="$d" output -raw dynamodb_file_metadata_table 2>/dev/null || echo "")"
  DDB_AUDIT="$(terraform -chdir="$d" output -raw dynamodb_audit_events_table 2>/dev/null || echo "")"
  DDB_NOTIF="$(terraform -chdir="$d" output -raw dynamodb_notifications_table 2>/dev/null || echo "")"
  DDB_FOLDERS="$(terraform -chdir="$d" output -raw dynamodb_folders_table 2>/dev/null || echo "")"
  DDB_VERSIONS="$(terraform -chdir="$d" output -raw dynamodb_file_versions_table 2>/dev/null || echo "")"
  DDB_SHARES="$(terraform -chdir="$d" output -raw dynamodb_file_shares_table 2>/dev/null || echo "")"
  IRSA_JSON="$(terraform -chdir="$d" output -json irsa_role_arns 2>/dev/null || echo "{}")"
  DB_USER="${DB_USER:-otterworks_admin}"
  if [ -z "${RDS_HOST}" ]; then
    warn "Terraform outputs unavailable; services will deploy without wired config."
  fi
  resolve_db_endpoint
}

# Where the *application* services send their SQL. Distinct from RDS_HOST, which
# stays pointed at the instance itself: creating and dropping databases is
# administrative work that has no business going through a connection pooler
# (CREATE/DROP DATABASE cannot run inside the transaction a pooled connection
# may already be in).
#
# Each service holds its own pool, so connections grow with tenants x services
# against a db.t3.micro that allows ~112 of them -- around ten awake tenants.
# PgBouncer in transaction mode makes that a function of concurrent SQL instead.
#
# Only used when the pooler is actually up: a tenant deployed against a
# nonexistent Service would fail every query, which is a far worse failure than
# using more connections than we would like. Set DB_VIA_PGBOUNCER=false to force
# services back onto the instance directly.
resolve_db_endpoint() {
  DB_ENDPOINT_HOST="${RDS_HOST}"
  DB_ENDPOINT_PORT="${RDS_PORT}"
  # Schema migrations take session-level advisory locks, which a transaction
  # pooler breaks; they get the pooler's session-mode port instead. Same host,
  # so this is still one bounded set of connections to RDS.
  DB_SESSION_PORT="${RDS_PORT}"

  [ "${DB_VIA_PGBOUNCER:-true}" = "true" ] || return 0
  kubectl -n "${PGBOUNCER_NAMESPACE:-otterworks-platform}" get svc pgbouncer >/dev/null 2>&1 || {
    warn "pgbouncer not found; wiring services straight to RDS (install with demo-platform/scripts/install-pgbouncer.sh)"
    return 0
  }

  DB_ENDPOINT_HOST="pgbouncer.${PGBOUNCER_NAMESPACE:-otterworks-platform}.svc.cluster.local"
  DB_ENDPOINT_PORT=6432
  DB_SESSION_PORT=6433
}

irsa_arn() { echo "${IRSA_JSON:-{}}" | jq -r --arg s "$1" '.[$s] // empty' 2>/dev/null; }

# Turn a per-tenant DB name (otterworks_a01) into an RFC-1123 fragment usable in
# Kubernetes resource names (otterworks-a01) so per-tenant Jobs/Secrets are named
# uniquely and concurrent teardowns don't collide on a shared resource name.
k8s_name_fragment() { printf '%s' "$1" | tr '[:upper:]_' '[:lower:]-'; }

# Create/replace a db-admin secret in a namespace WITHOUT ever putting the
# password on a process argv: the value is base64'd via a stdin pipe and the
# manifest is applied via stdin (heredoc), so it never appears in ps/cmdline.
# Requires DB_PASSWORD in the environment. Secret name defaults to
# tenant-db-admin but callers sharing a namespace (e.g. the reaper/teardown
# system namespace) MUST pass a unique name to avoid clobbering each other.
apply_db_admin_secret() {
  local ns="$1" name="${2:-tenant-db-admin}" b64
  b64="$(printf '%s' "${DB_PASSWORD}" | base64 | tr -d '\n')"
  kubectl -n "${ns}" apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: ${name}
type: Opaque
data:
  PGPASSWORD: ${b64}
EOF
}

# Tenant pods never get the RDS master login (DB_USER). Each tenant gets its own
# login role that owns only otterworks_<id>; the master login stays in the
# short-lived deploy/teardown/reaper Jobs below, which need it to create and
# drop databases and roles. Identifiers are capped at 63 bytes by Postgres,
# which would silently truncate a long name, so overlong names are shortened
# with a hash suffix instead of colliding.
tenant_db_role() {
  local r="$1_app" h
  if [ "${#r}" -gt 63 ]; then
    h="$(printf '%s' "$1" | sha256sum | cut -c1-8)"
    r="${1:0:50}_${h}_app"
  fi
  printf '%s' "${r}"
}

# Per-tenant server-side connection ceiling (direct-to-RDS and pooled alike).
TENANT_DB_CONN_LIMIT="${TENANT_DB_CONN_LIMIT:-30}"
TENANT_DB_SECRET="tenant-db-app"

# Hex only: it is embedded in PgBouncer's quoted userlist format and in URLs.
gen_db_password() { od -An -N24 -tx1 /dev/urandom | tr -d ' \n'; }

# Load the tenant's own DB credential from ${ns}/tenant-db-app into
# T_DB_USER/T_DB_PASSWORD. Returns non-zero if it does not exist yet.
load_tenant_db_credential() {
  local ns="$1" json
  json="$(kubectl -n "${ns}" get secret "${TENANT_DB_SECRET}" -o json 2>/dev/null)" || return 1
  T_DB_USER="$(printf '%s' "${json}" | jq -r '.data.username // empty | @base64d')"
  T_DB_PASSWORD="$(printf '%s' "${json}" | jq -r '.data.password // empty | @base64d')"
  [ -n "${T_DB_USER}" ] && [ -n "${T_DB_PASSWORD}" ]
}

# Reuse the tenant's existing credential (stable across redeploys, so running
# pods and the pooler stay in sync) or mint one and store it in the tenant
# namespace. The password goes to kubectl on stdin, never on an argv.
ensure_tenant_db_credential() {
  local ns="$1" db="$2" role
  role="$(tenant_db_role "${db}")"
  if load_tenant_db_credential "${ns}" && [ "${T_DB_USER}" = "${role}" ]; then
    return 0
  fi
  T_DB_USER="${role}"
  T_DB_PASSWORD="$(gen_db_password)"
  kubectl -n "${ns}" apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: ${TENANT_DB_SECRET}
type: Opaque
data:
  username: $(printf '%s' "${T_DB_USER}" | base64 | tr -d '\n')
  password: $(printf '%s' "${T_DB_PASSWORD}" | base64 | tr -d '\n')
EOF
}

# psql script (run as the RDS master login, connected to the `otterworks`
# bootstrap database) that provisions tenant database $1 for role $2. The role
# password is read from $TENANT_DB_PASSWORD inside the Job, so the script itself
# holds no secret. Idempotent, and also migrates a pre-existing tenant whose
# database and objects are still owned by the master login.
tenant_db_provision_sql() {
  local db="$1" role="$2" limit="${3:-${TENANT_DB_CONN_LIMIT}}"
  cat <<SQL
\\set ON_ERROR_STOP on
\\set db '${db}'
\\set role '${role}'
\\set conn_limit ${limit}
\\getenv app_password TENANT_DB_PASSWORD
SELECT coalesce(length(:'app_password'), 0) < 16 AS weak_password \\gset
\\if :weak_password
DO \$\$BEGIN RAISE EXCEPTION 'TENANT_DB_PASSWORD is missing or too short'; END\$\$;
\\endif

-- Login role: no CREATEDB/CREATEROLE, bounded fan-out. INHERIT stays on: the
-- role belongs to nothing but the implicit pg_database_owner, which is how a
-- database owner gets CREATE on the public schema in PG15+.
SELECT format('CREATE ROLE %I LOGIN', :'role')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role') \\gexec
SELECT format('ALTER ROLE %I WITH LOGIN NOCREATEDB NOCREATEROLE INHERIT CONNECTION LIMIT %s',
              :'role', :conn_limit) \\gexec
SELECT format('ALTER ROLE %I PASSWORD %L', :'role', :'app_password') \\gexec
-- The master login must be able to act as the role to hand it the database,
-- and later to drop it.
SELECT format('GRANT %I TO %I', :'role', current_user)
 WHERE NOT pg_has_role(current_user, :'role', 'USAGE') \\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'role')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db') \\gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', :'db', :'role')
  FROM pg_database WHERE datname = :'db'
   AND datdba <> (SELECT oid FROM pg_roles WHERE rolname = :'role') \\gexec
-- CONNECT/TEMP are granted to PUBLIC by default; only the owner keeps them.
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'db') \\gexec
-- Same for the bootstrap DB and any tenant DB not yet migrated to its own role,
-- so a tenant login can't even open a session there.
SELECT format('REVOKE CONNECT, TEMPORARY ON DATABASE %I FROM PUBLIC', datname)
  FROM pg_database
 WHERE datname ~ '^otterworks(_|\$)'
   AND datdba = (SELECT oid FROM pg_roles WHERE rolname = current_user) \\gexec
-- analytics-service keeps its tables in an \`analytics\` schema and asks for it
-- with the JDBC \`currentSchema\` option, which PgBouncer never forwards. A
-- database-level default is applied by the server itself and so survives
-- pooling. public stays first: everything else in this app lives there.
SELECT format('ALTER DATABASE %I SET search_path = public, analytics', :'db') \\gexec

-- Tenants created before per-tenant roles have every table owned by the master
-- login. Hand those objects to the tenant role so its migrations keep working.
\\connect :db
SELECT set_config('otterworks.tenant_role', :'role', false) \\gset
DO \$\$
DECLARE
  r   record;
  tgt text := current_setting('otterworks.tenant_role');
  me  oid  := (SELECT oid FROM pg_roles WHERE rolname = current_user);
BEGIN
  FOR r IN SELECT n.nspname FROM pg_namespace n
            WHERE n.nspowner = me AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
              AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_namespace'::regclass
                                AND d.objid = n.oid AND d.deptype = 'e') LOOP
    EXECUTE format('ALTER SCHEMA %I OWNER TO %I', r.nspname, tgt);
  END LOOP;
  -- Sequences owned by a column follow their table and are skipped here.
  FOR r IN SELECT c.oid::regclass AS obj, c.relkind FROM pg_class c
             JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relowner = me AND c.relkind IN ('r','p','v','m','f','S')
              AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
              AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_class'::regclass
                                AND d.objid = c.oid AND d.deptype IN ('e','a','i')) LOOP
    EXECUTE format('ALTER %s %s OWNER TO %I',
      CASE r.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
                     WHEN 'f' THEN 'FOREIGN TABLE' WHEN 'S' THEN 'SEQUENCE' ELSE 'TABLE' END,
      r.obj, tgt);
  END LOOP;
  FOR r IN SELECT p.oid::regprocedure AS obj, p.prokind FROM pg_proc p
             JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE p.proowner = me AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
              AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_proc'::regclass
                                AND d.objid = p.oid AND d.deptype = 'e') LOOP
    EXECUTE format('ALTER %s %s OWNER TO %I',
      CASE r.prokind WHEN 'p' THEN 'PROCEDURE' WHEN 'a' THEN 'AGGREGATE' ELSE 'FUNCTION' END,
      r.obj, tgt);
  END LOOP;
  FOR r IN SELECT t.oid::regtype AS obj, t.typtype FROM pg_type t
             JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE t.typowner = me AND t.typtype IN ('e','d','r','c')
              AND (t.typtype <> 'c' OR (SELECT relkind FROM pg_class WHERE oid = t.typrelid) = 'c')
              AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
              AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_type'::regclass
                                AND d.objid = t.oid AND d.deptype = 'e') LOOP
    EXECUTE format('ALTER %s %s OWNER TO %I',
      CASE r.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END, r.obj, tgt);
  END LOOP;
END
\$\$;
SQL
}

# psql script (master login, `otterworks` DB) that drops tenant database $1 and
# its login role $2. Idempotent; DROP OWNED clears any grants the role still
# holds so DROP ROLE isn't blocked by them.
tenant_db_drop_sql() {
  local db="$1" role="$2"
  cat <<SQL
\\set ON_ERROR_STOP on
\\set db '${db}'
\\set role '${role}'
SELECT format('DROP DATABASE IF EXISTS %I WITH (FORCE)', :'db') \\gexec
SELECT format('DROP OWNED BY %I', :'role') FROM pg_roles WHERE rolname = :'role' \\gexec
SELECT format('DROP ROLE %I', :'role') FROM pg_roles WHERE rolname = :'role' \\gexec
SQL
}

# psql script (master login) that drops per-tenant login roles which no longer
# own a database: left behind when a drop Job removed the database but not the
# role, or provisioning died between the two. A role owning nothing is unusable,
# so no control-table lookup is needed. Only roles the master login was granted
# (i.e. that tenant provisioning created) are candidates. Errors on one role
# don't stop the rest.
tenant_db_orphan_roles_sql() {
  cat <<'SQL'
\set ON_ERROR_STOP off
SELECT format('DROP OWNED BY %I', r.rolname), format('DROP ROLE %I', r.rolname)
  FROM pg_roles r
 WHERE r.rolname LIKE 'otterworks\_%\_app'
   AND r.rolcanlogin
   AND pg_has_role(current_user, r.oid, 'USAGE')
   AND NOT EXISTS (SELECT 1 FROM pg_database d WHERE d.datdba = r.oid) \gexec
SQL
}

# Run a psql script as the RDS master login from a short-lived Job in ${ns}.
# The script rides in a ConfigMap, so it must hold no secrets; the master
# password reaches the pod only via a Secret applied on stdin. Extra env vars can
# be wired from Secrets in ${ns} as NAME=secret:key. Requires
# RDS_HOST/RDS_PORT/DB_USER/DB_PASSWORD (load_infra_outputs + caller).
run_db_admin_job() {
  local ns="$1" job="$2" timeout="$3" sql="$4"; shift 4
  local secret="${job}-admin" envs="" spec name ref ok=1
  for spec in "$@"; do
    name="${spec%%=*}"; ref="${spec#*=}"
    envs+=$'\n'"            - name: ${name}"$'\n'"              valueFrom: { secretKeyRef: { name: ${ref%%:*}, key: ${ref#*:} } }"
  done
  apply_db_admin_secret "${ns}" "${secret}"
  kubectl -n "${ns}" delete job "${job}" --ignore-not-found >/dev/null 2>&1 || true
  SQL_TEXT="${sql}" jq -n --arg n "${job}" \
      '{apiVersion:"v1",kind:"ConfigMap",metadata:{name:$n},data:{"script.sql":$ENV.SQL_TEXT}}' \
    | kubectl -n "${ns}" apply -f - >/dev/null
  # shellcheck disable=SC2153  # RDS_HOST/RDS_PORT/DB_USER come from load_infra_outputs
  kubectl apply -n "${ns}" -f - >/dev/null <<YAML
apiVersion: batch/v1
kind: Job
metadata:
  name: ${job}
spec:
  backoffLimit: 1
  ttlSecondsAfterFinished: 120
  template:
    spec:
      restartPolicy: Never
      volumes:
        - name: sql
          configMap: { name: ${job} }
      containers:
        - name: psql
          image: postgres:16-alpine
          env:
            - name: PGPASSWORD
              valueFrom: { secretKeyRef: { name: ${secret}, key: PGPASSWORD } }${envs}
          volumeMounts:
            - { name: sql, mountPath: /sql, readOnly: true }
          command: ["psql"]
          args:
            - "host=${RDS_HOST} port=${RDS_PORT} dbname=otterworks user=${DB_USER} sslmode=prefer connect_timeout=10"
            - "-X"
            - "-q"
            - "-f"
            - "/sql/script.sql"
          resources:
            requests: { cpu: 50m, memory: 64Mi }
            limits: { cpu: 200m, memory: 128Mi }
YAML
  if kubectl -n "${ns}" wait --for=condition=complete "job/${job}" --timeout="${timeout}" >/dev/null 2>&1; then
    ok=0
  else
    warn "  job ${ns}/${job} did not complete; last log lines:"
    kubectl -n "${ns}" logs "job/${job}" 2>/dev/null | tail -5 || true
  fi
  kubectl -n "${ns}" delete secret "${secret}" --ignore-not-found >/dev/null 2>&1 || true
  kubectl -n "${ns}" delete configmap "${job}" --ignore-not-found >/dev/null 2>&1 || true
  kubectl -n "${ns}" delete job "${job}" --ignore-not-found >/dev/null 2>&1 || true
  return "${ok}"
}

# PgBouncer authenticates clients against its own auth_file before opening a
# server connection, so each tenant login needs a line in the shared
# pgbouncer-auth Secret. `pgbouncer_userlist_set ROLE [PASSWORD]` upserts (or,
# without a password, removes) ROLE's line. kubectl replace carries the read
# resourceVersion, so concurrent deploys retry instead of dropping each other's
# line. The content travels via stdin/env, never argv.
# Returns 0 if written, 1 if already up to date, 2 if there is no pooler.
pgbouncer_userlist_set() {
  local role="$1" pw="${2:-}" ns="${PGBOUNCER_NAMESPACE:-otterworks-platform}" json cur new i
  for i in 1 2 3 4 5; do
    json="$(kubectl -n "${ns}" get secret pgbouncer-auth -o json 2>/dev/null)" || return 2
    cur="$(printf '%s' "${json}" | jq -r '.data["userlist.txt"] // "" | @base64d' | sed '/^[[:space:]]*$/d')"
    new="$(printf '%s\n' "${cur}" | awk -v r="\"${role}\"" '$1 != r' | sed '/^[[:space:]]*$/d')"
    if [ -n "${pw}" ]; then
      new="$(printf '%s\n"%s" "%s"' "${new}" "${role}" "${pw}" | sed '/^[[:space:]]*$/d')"
    fi
    [ "${new}" = "${cur}" ] && return 1
    if printf '%s' "${json}" \
         | USERLIST="${new}"$'\n' jq '.data["userlist.txt"] = ($ENV.USERLIST | @base64) | del(.metadata.managedFields)' \
         | kubectl replace -f - >/dev/null 2>&1; then
      return 0
    fi
    sleep "${i}"
  done
  warn "  could not update ${ns}/pgbouncer-auth after ${i} attempts"
  return 3
}

# PgBouncer reads auth_file only at start (and on RELOAD); a Secret changing
# underneath it is not picked up. Roll the pooler so a new login is accepted.
restart_pgbouncer() {
  local ns="${PGBOUNCER_NAMESPACE:-otterworks-platform}"
  log "  restarting pgbouncer so it picks up the new tenant login..."
  if ! { kubectl -n "${ns}" rollout restart deploy/pgbouncer >/dev/null \
         && kubectl -n "${ns}" rollout status deploy/pgbouncer --timeout=180s >/dev/null; }; then
    warn "  pgbouncer restart did not finish; check: kubectl -n ${ns} rollout status deploy/pgbouncer"
  fi
}

# Drop a per-tenant database and its login role via an in-cluster Job in
# ${run_ns}. Callers MUST delete the tenant namespace first so no application
# pods are still connected (otherwise DROP DATABASE races the pods'
# connection-pool reconnects). Requires load_infra_outputs to have set
# RDS_HOST/RDS_PORT/DB_USER, and DB_PASSWORD set.
drop_tenant_db() {
  local db="$1" run_ns="$2" role frag
  role="$(tenant_db_role "${db}")"
  frag="$(k8s_name_fragment "${db}")"
  if run_db_admin_job "${run_ns}" "tenant-db-drop-${frag}" 90s "$(tenant_db_drop_sql "${db}" "${role}")"; then
    log "  database ${db} and role ${role} dropped."
  else
    return 1
  fi
  # The role no longer exists, so its line is dead weight; it is dropped from
  # the pooler's file at its next restart, no restart needed now.
  pgbouncer_userlist_set "${role}" || true
  return 0
}

# Secret handling: values are collected into SECRET_KV and later written to a
# locked-down temp values file passed to helm via -f, so secret values never
# appear in the process argument list (ps / /proc/*/cmdline). Mirrors deploy-dev.sh.
add_secret() { SECRET_KV+=("$1" "$2"); }
urlencode()  { jq -rn --arg s "$1" '$s|@uri'; }

# Build per-service Helm --set flags (EXTRA_ARGS) + secret pairs (SECRET_KV) for
# a tenant. Requires these tenant-scoped globals to be set by the caller:
#   T_REDIS_HOST, T_MEILI_URL, T_DB_NAME, T_WIRE_EVENTING (true/false),
#   T_DB_USER/T_DB_PASSWORD (the tenant's own login; never the RDS master one)
build_helm_args() {
  local service=$1
  EXTRA_ARGS=()
  SECRET_KV=()

  # replicas=1 (cost control) and disable the per-service NetworkPolicy — the
  # tenant namespace ships ONE NetworkPolicy that allows intra-namespace traffic.
  EXTRA_ARGS+=(--set replicaCount=1 --set networkPolicy.enabled=false)
  # Force ClusterIP for EVERY service so no tenant gets its own LoadBalancer/ELB
  # (some charts, e.g. api-gateway, default to LoadBalancer). External access is
  # only ever through the ONE shared ingress. See docs/MULTI-TENANT-DEMO-PLAN.md §3.
  EXTRA_ARGS+=(--set service.type=ClusterIP)

  local role; role="$(irsa_arn "$service")"
  if [ -n "$role" ]; then EXTRA_ARGS+=(--set "serviceAccount.roleArn=${role}"); fi
  if [[ " ${JVM_SERVICES} " == *" ${service} "* ]]; then
    EXTRA_ARGS+=(--set resources.requests.memory=512Mi --set resources.limits.memory=1024Mi --set resources.limits.cpu=1000m)
  fi

  case "$service" in
    web-app|admin-dashboard)
      # SHARED ingress: frontends are ClusterIP (set above) + per-tenant ingress.
      EXTRA_ARGS+=(--set ingress.enabled=false)
      EXTRA_ARGS+=(--set-string config.API_GATEWAY_URL=http://api-gateway:8080)
      return 0 ;;
  esac

  local port="${CONTAINER_PORT[$service]:-}"
  if [ -n "$port" ]; then EXTRA_ARGS+=(--set "service.port=${port}" --set "service.targetPort=${port}"); fi
  EXTRA_ARGS+=(--set ingress.enabled=false)

  if [ -n "${JWT_SECRET}" ]; then
    case "$service" in
      api-gateway|auth-service|document-service|collab-service|admin-service)
        add_secret JWT_SECRET "${JWT_SECRET}" ;;
    esac
  fi

  local sns_topic=""; local sqs_notif=""
  if [ "${T_WIRE_EVENTING}" = "true" ]; then
    sns_topic="${SNS_TOPIC:-}"; sqs_notif="${SQS_NOTIF:-}"
  fi

  case "$service" in
    api-gateway)
      EXTRA_ARGS+=(--set-string "config.REDIS_HOST=${T_REDIS_HOST}" --set-string "config.REDIS_PORT=6379") ;;
    auth-service)
      EXTRA_ARGS+=(--set-string "config.SPRING_PROFILES_ACTIVE=prod")
      EXTRA_ARGS+=(--set-string "config.SPRING_DATASOURCE_URL=jdbc:postgresql://${DB_ENDPOINT_HOST}:${DB_ENDPOINT_PORT}/${T_DB_NAME}")
      EXTRA_ARGS+=(--set-string "config.SPRING_DATASOURCE_USERNAME=${T_DB_USER}")
      # Flyway runs on boot and holds a session-level advisory lock for the
      # length of the migration, so it gets its own datasource on the pooler's
      # session port; the application's own queries stay on the transaction one.
      EXTRA_ARGS+=(--set-string "config.SPRING_FLYWAY_URL=jdbc:postgresql://${DB_ENDPOINT_HOST}:${DB_SESSION_PORT}/${T_DB_NAME}")
      EXTRA_ARGS+=(--set-string "config.SPRING_FLYWAY_USER=${T_DB_USER}")
      add_secret SPRING_FLYWAY_PASSWORD "${T_DB_PASSWORD}"
      add_secret SPRING_DATASOURCE_PASSWORD "${T_DB_PASSWORD}" ;;
    file-service)
      EXTRA_ARGS+=(--set-string "config.AWS_REGION=${AWS_REGION}")
      EXTRA_ARGS+=(--set-string "config.S3_BUCKET=${S3_FILE_BUCKET}")
      EXTRA_ARGS+=(--set-string "config.DYNAMODB_TABLE=${DDB_FILE_META}")
      EXTRA_ARGS+=(--set-string "config.DYNAMODB_FOLDERS_TABLE=${DDB_FOLDERS}")
      EXTRA_ARGS+=(--set-string "config.DYNAMODB_VERSIONS_TABLE=${DDB_VERSIONS}")
      EXTRA_ARGS+=(--set-string "config.DYNAMODB_SHARES_TABLE=${DDB_SHARES}")
      EXTRA_ARGS+=(--set-string "config.REDIS_HOST=${T_REDIS_HOST}" --set-string "config.REDIS_PORT=6379")
      EXTRA_ARGS+=(--set-string "config.SNS_TOPIC_ARN=${sns_topic}") ;;
    document-service)
      EXTRA_ARGS+=(--set-string "config.REDIS_HOST=${T_REDIS_HOST}" --set-string "config.REDIS_PORT=6379")
      EXTRA_ARGS+=(--set-string "config.DOC_SVC_AWS_REGION=${AWS_REGION}")
      EXTRA_ARGS+=(--set-string "config.DOC_SVC_SNS_TOPIC_ARN=${sns_topic}")
      add_secret DOC_SVC_DATABASE_URL "postgresql+asyncpg://$(urlencode "${T_DB_USER}"):$(urlencode "${T_DB_PASSWORD}")@${DB_ENDPOINT_HOST}:${DB_ENDPOINT_PORT}/${T_DB_NAME}" ;;
    collab-service)
      EXTRA_ARGS+=(--set-string "config.HTTP_PORT=8084" --set-string "config.NODE_ENV=production")
      EXTRA_ARGS+=(--set-string "config.REDIS_HOST=${T_REDIS_HOST}" --set-string "config.REDIS_PORT=6379") ;;
    notification-service)
      EXTRA_ARGS+=(--set-string "config.AWS_REGION=${AWS_REGION}")
      EXTRA_ARGS+=(--set-string "config.REDIS_HOST=${T_REDIS_HOST}" --set-string "config.REDIS_PORT=6379")
      EXTRA_ARGS+=(--set-string "config.DYNAMODB_TABLE_NOTIFICATIONS=${DDB_NOTIF}")
      if [ -n "${DDB_NOTIF_PREFS:-}" ]; then EXTRA_ARGS+=(--set-string "config.DYNAMODB_TABLE_PREFERENCES=${DDB_NOTIF_PREFS}"); fi
      EXTRA_ARGS+=(--set-string "config.SNS_TOPIC_ARN=${sns_topic}")
      EXTRA_ARGS+=(--set-string "config.SQS_QUEUE_URL=${sqs_notif}") ;;
    search-service)
      EXTRA_ARGS+=(--set-string "config.AWS_REGION=${AWS_REGION}")
      EXTRA_ARGS+=(--set-string "config.REDIS_HOST=${T_REDIS_HOST}" --set-string "config.REDIS_PORT=6379")
      EXTRA_ARGS+=(--set-string "config.HOST=0.0.0.0" --set-string "config.PORT=8087")
      EXTRA_ARGS+=(--set-string "config.MEILISEARCH_URL=${T_MEILI_URL}")
      EXTRA_ARGS+=(--set-string "config.REQUIRE_AUTH=false" --set-string "config.SQS_ENABLED=false") ;;
    analytics-service)
      EXTRA_ARGS+=(--set-string "config.AWS_REGION=${AWS_REGION}")
      # Drop the nightly usage-rollup CronJob for ephemeral tenants: it is the
      # batch->event-driven demo's "before" state, unrelated to multi-tenant
      # isolation, and just burns ResourceQuota on short-lived tenants.
      EXTRA_ARGS+=(--set cronjob.enabled=false)
      EXTRA_ARGS+=(--set-string "config.ANALYTICS_HOST=0.0.0.0" --set-string "config.PORT=8088")
      # Third migration path, and the quietest: AnalyticsDb.migrate() runs Flyway
      # from the same DATABASE_URL as the Slick pool, and a failed migration
      # falls back to the in-memory store instead of crashing -- so getting this
      # wrong loses the tenant's analytics data without any pod ever going
      # unhealthy. Session port for the whole service, as with Rails. Slick here
      # opens connections per query rather than holding a pool, so this costs
      # the session pooler far less than the connection count suggests.
      EXTRA_ARGS+=(--set-string "config.DATABASE_URL=jdbc:postgresql://${DB_ENDPOINT_HOST}:${DB_SESSION_PORT}/${T_DB_NAME}")
      EXTRA_ARGS+=(--set-string "config.DATABASE_USER=${T_DB_USER}")
      add_secret DATABASE_PASSWORD "${T_DB_PASSWORD}" ;;
    admin-service)
      # Rails takes a session-level advisory lock in `db:migrate`, which runs
      # from the image's CMD on every boot and shares one connection URL with
      # the app -- so the whole service uses the session-mode port.
      EXTRA_ARGS+=(--set-string "config.DATABASE_HOST=${DB_ENDPOINT_HOST}" --set-string "config.DATABASE_PORT=${DB_SESSION_PORT}")
      EXTRA_ARGS+=(--set-string "config.DATABASE_USER=${T_DB_USER}")
      # database.yml names a shared admin_service_production database, which a
      # tenant login can't (and shouldn't) reach. Rails merges DATABASE_URL over
      # database.yml, so this only points it at the tenant's own database.
      EXTRA_ARGS+=(--set-string "config.DATABASE_URL=postgresql://${DB_ENDPOINT_HOST}:${DB_SESSION_PORT}/${T_DB_NAME}")
      EXTRA_ARGS+=(--set-string "config.RAILS_ENV=production" --set-string "config.RAILS_LOG_TO_STDOUT=true")
      add_secret DATABASE_PASSWORD "${T_DB_PASSWORD}"
      add_secret SECRET_KEY_BASE "${SECRET_KEY_BASE}" ;;
    audit-service)
      EXTRA_ARGS+=(--set-string "config.Aws__Region=${AWS_REGION}")
      EXTRA_ARGS+=(--set-string "config.Aws__DynamoDbTable=${DDB_AUDIT}")
      EXTRA_ARGS+=(--set-string "config.Aws__S3ArchiveBucket=${S3_AUDIT_BUCKET}") ;;
    report-service)
      EXTRA_ARGS+=(--set-string "config.DB_HOST=${DB_ENDPOINT_HOST}" --set-string "config.DB_PORT=${DB_ENDPOINT_PORT}")
      EXTRA_ARGS+=(--set-string "config.DB_NAME=${T_DB_NAME}" --set-string "config.DB_USER=${T_DB_USER}")
      add_secret DB_PASSWORD "${T_DB_PASSWORD}" ;;
  esac
}
