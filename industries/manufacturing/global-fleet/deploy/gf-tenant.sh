#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Global fleet tenants on the shared otterworks-dev cluster.
#
#   gf-tenant.sh up before [--run RUN] [--id ID]   JSF portal + its DB + source browser
#   gf-tenant.sh up after  [--run RUN] [--id ID]   fleet-service (uk, de) + frontend/fleet from this checkout
#   gf-tenant.sh reset [--run RUN]                 reload the fixed seed into both tenants
#   gf-tenant.sh down RUN                          tear down RUN's tenants, fail on any residue
#   gf-tenant.sh check TOKEN                       list what still bears TOKEN
#
# A run (default gf-r1027a) owns two tokens, <run>-before and <run>-after. The
# token is stamped on every resource: the demo/token label, ECR image tags and
# the control-table item. Tenant ids default to gf-before / gf-after for the
# default run and to the token itself for any other run.
# ------------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
GF_ROOT="$(cd "${HERE}/.." && pwd)"
REPO_ROOT="$(cd "${GF_ROOT}/../../.." && pwd)"
# shellcheck source=../../../../scripts/lib/tenant-common.sh
source "${REPO_ROOT}/scripts/lib/tenant-common.sh"

DEFAULT_RUN="gf-r1027a"
HOST_SUFFIX="${HOST_SUFFIX:-demo.otterworks.app}"
TTL_HOURS="${GF_TTL_HOURS:-72}"
MAVEN_MIRROR="${MAVEN_MIRROR:-https://repo.maven.apache.org/maven2}"
RDS_SECRET_ID="${RDS_SECRET_ID:-otterworks/dev/rds/master}"
CONTROL_TABLE="${CONTROL_TABLE:-otterworks-demo-control}"
TIMINGS_DIR="${GF_TIMINGS_DIR:-${HOME}/.gf-timings}"
ECR_PREFIX="otterworks"

CMD="${1:-}"; shift || true
SIDE=""; RUN="${DEFAULT_RUN}"; ID=""
case "${CMD}" in
  up)    SIDE="${1:-}"; shift || true ;;
  down)  RUN="${1:-}"; shift || true; [ -n "${RUN}" ] || { err "Usage: $0 down RUN"; exit 1; } ;;
  check) TOKEN="${1:-}"; shift || true; [ -n "${TOKEN}" ] || { err "Usage: $0 check TOKEN"; exit 1; } ;;
  reset) ;;
  *) sed -n '2,16p' "$0"; exit 1 ;;
esac
while [ $# -gt 0 ]; do
  case "$1" in
    --run) RUN="$2"; shift 2 ;;
    --id)  ID="$2"; shift 2 ;;
    *) err "Unknown argument: $1"; exit 1 ;;
  esac
done; [[ "${RUN}${ID:+-}${ID}" =~ ^[a-z0-9-]{1,40}$ ]] || { err "run and --id take lowercase letters, digits and dashes"; exit 1; }

require_bins aws kubectl jq docker
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
if [ -z "${KUBERNETES_SERVICE_HOST:-}" ]; then
  aws eks update-kubeconfig --name "${EKS_CLUSTER}" --region "${AWS_REGION}" --alias "${EKS_CLUSTER}" >/dev/null
fi

tenant_id_for() {
  local side="$1"
  if [ -n "${ID}" ]; then echo "${ID}"
  elif [ "${RUN}" = "${DEFAULT_RUN}" ]; then echo "gf-${side}"
  else echo "${RUN}-${side}"; fi
}

# ---------- timings ----------
TIMINGS=()
step() {
  local name="$1"; shift
  local t0 t1
  t0="$(date +%s.%N)"
  log "== ${name}"
  "$@"
  t1="$(date +%s.%N)"
  TIMINGS+=("$(printf '%s\t%.1f' "${name}" "$(echo "${t1} - ${t0}" | bc)")")
}
print_timings() {
  local label="$1" f total=0 row
  mkdir -p "${TIMINGS_DIR}"
  f="${TIMINGS_DIR}/${label}.tsv"
  printf 'step\tseconds\n' > "${f}"
  for row in "${TIMINGS[@]}"; do
    printf '%s\n' "${row}" >> "${f}"
    total="$(echo "${total} + ${row##*$'\t'}" | bc)"
  done
  printf 'total\t%s\n' "${total}" >> "${f}"
  log "Timings (${f}):"
  column -t -s $'\t' "${f}"
}

# ---------- shared pieces ----------
# DB admin credential: DB_PASSWORD from the environment, else the vaulted RDS
# secret, else the platform Secret the in-cluster runner uses. Never on argv.
load_db_admin() {
  local secret=""
  if [ -z "${DB_PASSWORD:-}" ]; then
    secret="$(aws secretsmanager get-secret-value --region "${AWS_REGION}" --secret-id "${RDS_SECRET_ID}" \
      --query SecretString --output text 2>/dev/null || true)"
    if [ -n "${secret}" ]; then
      RDS_HOST="$(printf '%s' "${secret}" | jq -r '.host // empty')"
      RDS_PORT="$(printf '%s' "${secret}" | jq -r '.port // 5432')"
      DB_USER="$(printf '%s' "${secret}" | jq -r '.username // empty')"
      DB_PASSWORD="$(printf '%s' "${secret}" | jq -r '.password // empty')"
    else
      DB_PASSWORD="$(kubectl -n "${PLATFORM_NAMESPACE:-otterworks-platform}" get secret "${PLATFORM_DB_SECRET:-demo-ops-dashboard}" \
        -o jsonpath='{.data.DB_PASSWORD}' 2>/dev/null | base64 -d || true)"
    fi
    unset secret
  fi
  if [ -z "${RDS_HOST:-}" ]; then
    local rds; rds="$(terraform -chdir="${REPO_ROOT}/infrastructure/terraform" output -raw rds_endpoint 2>/dev/null || true)"
    RDS_HOST="${rds%%:*}"
  fi
  RDS_PORT="${RDS_PORT:-5432}"
  DB_USER="${DB_USER:-otterworks_admin}"
  [ -n "${RDS_HOST}" ] && [ -n "${DB_PASSWORD}" ] || { err "no DB admin credential (set DB_PASSWORD)"; exit 1; }
  export RDS_HOST RDS_PORT DB_USER DB_PASSWORD
}

ecr_login() {
  aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}" >/dev/null
}

ensure_repo() {
  local repo="${ECR_PREFIX}/$1"
  aws ecr describe-repositories --region "${AWS_REGION}" --repository-names "${repo}" >/dev/null 2>&1 && return 0
  aws ecr create-repository --region "${AWS_REGION}" --repository-name "${repo}" \
    --image-scanning-configuration scanOnPush=true \
    --tags Key=platform/team,Value=otterworks Key=platform/environment,Value=dev >/dev/null
  aws ecr put-lifecycle-policy --region "${AWS_REGION}" --repository-name "${repo}" --lifecycle-policy-text \
    '{"rules":[{"rulePriority":1,"description":"expire untagged","selection":{"tagStatus":"untagged","countType":"sinceImagePushed","countUnit":"days","countNumber":7},"action":{"type":"expire"}}]}' >/dev/null
  log "  created ECR repository ${repo}"
}

# build_push <repo> <context> <dockerfile> [docker build args...]
build_push() {
  local name="$1" ctx="$2" file="$3"; shift 3
  local ref="${ECR_REGISTRY}/${ECR_PREFIX}/${name}:${TOKEN}"
  ensure_repo "${name}"
  docker build -q --platform linux/amd64 -t "${ref}" -f "${file}" \
    --label "demo/token=${TOKEN}" --label "demo/expires-at=${EXPIRES_AT}" "$@" "${ctx}" >/dev/null
  docker push -q "${ref}" >/dev/null
  log "  pushed ${ref}"
}

apply_namespace() {
  kubectl apply -f - >/dev/null <<YAML
apiVersion: v1
kind: Namespace
metadata:
  name: ${NS}
  labels:
    app.kubernetes.io/managed-by: otterworks-tenant
    platform/environment: dev
    platform/team: otterworks
    demo/tenant: "${TENANT_ID}"
    demo/token: "${TOKEN}"
    demo/profile: gf-${SIDE}
    kubernetes.io/metadata.name: ${NS}
  annotations:
    demo/expires-at: "${EXPIRES_AT}"
    demo/expires-at-epoch: "${EXPIRES_EPOCH}"
    demo/attendee-id: "${TENANT_ID}"
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: tenant-quota
  namespace: ${NS}
  labels: { demo/token: "${TOKEN}" }
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 3Gi
    limits.cpu: "4"
    limits.memory: 6Gi
    pods: "20"
---
apiVersion: v1
kind: LimitRange
metadata:
  name: tenant-limits
  namespace: ${NS}
  labels: { demo/token: "${TOKEN}" }
spec:
  limits:
    - type: Container
      default: { cpu: 500m, memory: 256Mi }
      defaultRequest: { cpu: 50m, memory: 64Mi }
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tenant-isolation
  namespace: ${NS}
  labels: { demo/token: "${TOKEN}" }
spec:
  podSelector: {}
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: ${NS} } }
        - namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: ${INGRESS_NAMESPACE} } }
        - namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: monitoring } }
YAML
}

# The reaper garbage-collects managed namespaces with no TENANT# item, so every
# tenant gets one, carrying its token and expiry.
put_control_item() {
  local now; now="$(date -u +%s)"
  aws dynamodb put-item --table-name "${CONTROL_TABLE}" --region "${AWS_REGION}" --item "$(jq -n \
    --arg id "${TENANT_ID}" --arg ns "${NS}" --arg db "${T_DB_NAME}" --arg url "https://${WEB_HOST}" \
    --arg branch "$(git -C "${REPO_ROOT}" rev-parse --abbrev-ref HEAD)" --arg token "${TOKEN}" \
    --arg exp "${EXPIRES_EPOCH}" --arg now "${now}" '{
      PK:{S:("TENANT#"+$id)}, SK:{S:"META"}, id:{S:$id}, namespace:{S:$ns}, db_name:{S:$db},
      url:{S:$url}, branch:{S:$branch}, token:{S:$token}, owner:{S:"gf-fixture"}, tier:{S:"A"},
      status:{S:"active"}, pinned:{BOOL:false}, persistent:{BOOL:false},
      created_at:{N:$now}, checked_out_at:{N:$now}, last_seen_at:{N:$now}, expires_at:{N:$exp}, was_running:{N:"0"}}')"
}

apply_db_secret() {
  local url="jdbc:postgresql://${RDS_HOST}:${RDS_PORT}/${T_DB_NAME}?sslmode=prefer"; ensure_app_credential; apply_db_admin_secret
  kubectl -n "${NS}" apply -f - >/dev/null <<YAML
apiVersion: v1
kind: Secret
metadata:
  name: fleet-db
  labels: { demo/token: "${TOKEN}" }
type: Opaque
data:
  PGPASSWORD: $(printf '%s' "${APP_DB_PASSWORD}" | base64 | tr -d '\n')
  DB_PASSWORD: $(printf '%s' "${APP_DB_PASSWORD}" | base64 | tr -d '\n')
  SPRING_DATASOURCE_PASSWORD: $(printf '%s' "${APP_DB_PASSWORD}" | base64 | tr -d '\n')
stringData:
  PGHOST: "${RDS_HOST}"
  PGPORT: "${RDS_PORT}"
  PGUSER: "${APP_DB_USER}"
  PGDATABASE: "${T_DB_NAME}"
  DB_URL: "${url}"
  DB_USER: "${APP_DB_USER}"
  SPRING_DATASOURCE_URL: "${url}"
  SPRING_DATASOURCE_USERNAME: "${APP_DB_USER}"
YAML
}

# run_job <name> <image> <script>
run_job() {
  local name="$1" image="$2" script="$3"
  kubectl -n "${NS}" delete job "${name}" --ignore-not-found >/dev/null 2>&1 || true
  kubectl -n "${NS}" apply -f - >/dev/null <<YAML
apiVersion: batch/v1
kind: Job
metadata:
  name: ${name}
  labels: { demo/token: "${TOKEN}" }
spec:
  backoffLimit: 1
  template:
    metadata:
      labels: { demo/token: "${TOKEN}" }
    spec:
      restartPolicy: Never
      containers:
        - name: psql
          image: ${image}
          envFrom: [ { secretRef: { name: fleet-db-admin } } ]
          command: ["/bin/sh", "-c"]
          args:
            - |
$(printf '%s\n' "${script}" | sed 's/^/              /')
          resources:
            requests: { cpu: 50m, memory: 64Mi }
            limits: { cpu: 500m, memory: 256Mi }
YAML
  if ! kubectl -n "${NS}" wait --for=condition=complete "job/${name}" --timeout=300s >/dev/null; then
    kubectl -n "${NS}" logs "job/${name}" --tail=20 || true
    err "job ${name} failed"; return 1
  fi
  kubectl -n "${NS}" logs "job/${name}" --tail=5 | sed 's/^/  /'
  kubectl -n "${NS}" delete job "${name}" --ignore-not-found >/dev/null
}

create_database() {
  run_job gf-db-create "postgres:16-alpine" "set -e
if psql -d otterworks -tAc \"SELECT 1 FROM pg_database WHERE datname='${T_DB_NAME}'\" | grep -q 1; then
  echo \"database ${T_DB_NAME} exists\"
else
  psql -d otterworks -v ON_ERROR_STOP=1 -c 'CREATE DATABASE \"${T_DB_NAME}\"'
  psql -d otterworks -c \"COMMENT ON DATABASE \\\"${T_DB_NAME}\\\" IS 'demo/token=${TOKEN} expires=${EXPIRES_AT}'\"
fi"; create_app_role
}

load_seed() {
  run_job gf-seed "${ECR_REGISTRY}/${ECR_PREFIX}/gf-seed:${TOKEN}" "set -e
psql -v ON_ERROR_STOP=1 -q -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
psql -v ON_ERROR_STOP=1 -q -f /seed/001_schema.sql
psql -v ON_ERROR_STOP=1 -q -f /seed/002_seed.sql
psql -tAc \"SELECT 'seeded ' || (SELECT count(*) FROM employee) || ' employees, ' || (SELECT count(*) FROM vehicle) || ' vehicles'\""; grant_app_role
}

# deploy_app <name> <image> <port> <health path> <cpu req> <mem req> <cpu lim> <mem lim> [env-from-db]
deploy_app() {
  local name="$1" image="$2" port="$3" health="$4" rc="$5" rm="$6" lc="$7" lm="$8" db="${9:-}"
  local envfrom=""
  [ -n "${db}" ] && envfrom="          envFrom: [ { secretRef: { name: fleet-db } } ]"
  kubectl -n "${NS}" apply -f - >/dev/null <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${name}
  labels: { app: ${name}, demo/token: "${TOKEN}" }
spec:
  replicas: 1
  selector: { matchLabels: { app: ${name} } }
  template:
    metadata:
      labels: { app: ${name}, demo/token: "${TOKEN}" }
    spec:
      containers:
        - name: ${name}
          image: ${image}
          imagePullPolicy: Always
          ports: [ { containerPort: ${port} } ]
${envfrom}
          readinessProbe: { httpGet: { path: "${health}", port: ${port} }, initialDelaySeconds: 5, periodSeconds: 5, failureThreshold: 60 }
          livenessProbe: { httpGet: { path: "${health}", port: ${port} }, initialDelaySeconds: 120, periodSeconds: 20 }
          resources:
            requests: { cpu: ${rc}, memory: ${rm} }
            limits: { cpu: ${lc}, memory: ${lm} }
---
apiVersion: v1
kind: Service
metadata:
  name: ${name}
  labels: { app: ${name}, demo/token: "${TOKEN}" }
spec:
  type: ClusterIP
  selector: { app: ${name} }
  ports: [ { port: 80, targetPort: ${port} } ]
YAML
}

wait_rollouts() {
  local d
  for d in "$@"; do kubectl -n "${NS}" rollout status "deploy/${d}" --timeout=600s; done
}

# apply_ingress <host> <svc> [<host> <svc>]... ; "<host>/api" routes /api on that host.
apply_ingress() {
  local rules="" host svc path
  while [ $# -gt 0 ]; do
    host="$1"; svc="$2"; shift 2; path="/"
    case "${host}" in */*) path="/${host#*/}"; host="${host%%/*}" ;; esac
    rules="${rules}
    - host: ${host}
      http:
        paths:
          - path: ${path}
            pathType: Prefix
            backend: { service: { name: ${svc}, port: { number: 80 } } }"
  done
  kubectl -n "${NS}" apply -f - >/dev/null <<YAML
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tenant-ingress
  labels: { demo/token: "${TOKEN}" }
spec:
  ingressClassName: nginx
  rules:${rules}
YAML
}

# Resolve through a public resolver: the local one caches the NXDOMAIN it got
# before external-dns created the record.
wait_https() {
  local url="$1" host ip _ resolve=()
  host="${url#https://}"; host="${host%%/*}"
  for _ in $(seq 1 60); do
    resolve=()
    if command -v dig >/dev/null 2>&1; then
      ip="$(dig +short @"${PUBLIC_RESOLVER:-8.8.8.8}" "${host}" A | grep -E '^[0-9.]+$' | head -1 || true)"
      [ -n "${ip}" ] && resolve=(--resolve "${host}:443:${ip}")
    fi
    if [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "${resolve[@]}" "${url}")" = "200" ]; then
      log "  ${url} -> 200"; return 0
    fi
    sleep 10
  done
  err "${url} did not answer 200 within 10 minutes"; return 1
}

set_tenant() {
  SIDE="$1"
  TOKEN="${RUN}-${SIDE}"
  TENANT_ID="$(tenant_id_for "${SIDE}")"
  NS="$(tenant_namespace "${TENANT_ID}")"
  T_DB_NAME="$(tenant_db_name "${TENANT_ID}")"
  WEB_HOST="t-${TENANT_ID}.${HOST_SUFFIX}"
  SRC_HOST="src-t-${TENANT_ID}.${HOST_SUFFIX}"
  EXPIRES_EPOCH="$(( $(date -u +%s) + TTL_HOURS * 3600 ))"
  EXPIRES_AT="$(date -u -d "@${EXPIRES_EPOCH}" +%Y-%m-%dT%H:%M:%SZ)"
}

# ---------- commands ----------
up_before() {
  set_tenant before
  log "Tenant ${TENANT_ID} (${NS}), token ${TOKEN}, expires ${EXPIRES_AT}"
  load_db_admin; ecr_login
  step "build+push gf-fleet-portal" build_push gf-fleet-portal "${GF_ROOT}/jsf-portal" "${GF_ROOT}/jsf-portal/Dockerfile" \
    --build-arg "MAVEN_MIRROR=${MAVEN_MIRROR}"
  step "build+push gf-source-browser" build_push gf-source-browser "${GF_ROOT}" "${GF_ROOT}/source-browser/Dockerfile"
  step "build+push gf-seed" build_push gf-seed "${GF_ROOT}" "${HERE}/seed.Dockerfile"
  step "namespace+quota+netpol" apply_namespace
  step "control-table item" put_control_item
  step "db secret" apply_db_secret
  step "create database" create_database
  step "load seed" load_seed
  step "deploy portal+browser" deploy_before_apps
  step "ingress" apply_ingress "${WEB_HOST}" fleet-portal "${SRC_HOST}" source-browser
  step "rollout" wait_rollouts fleet-portal source-browser
  step "https ${WEB_HOST}" wait_https "https://${WEB_HOST}/health"
  step "https ${SRC_HOST}" wait_https "https://${SRC_HOST}/health"
  print_timings "${TOKEN}-up"
  log "Portal:         https://${WEB_HOST}/"
  log "Source browser: https://${SRC_HOST}/"
}
deploy_before_apps() {
  deploy_app fleet-portal "${ECR_REGISTRY}/${ECR_PREFIX}/gf-fleet-portal:${TOKEN}" 8080 /health 100m 384Mi 1 768Mi db
  deploy_app source-browser "${ECR_REGISTRY}/${ECR_PREFIX}/gf-source-browser:${TOKEN}" 8080 /health 10m 16Mi 100m 64Mi
}

# The portal and fleet-service connect as a per-tenant role that owns only its
# own database. Jobs (create, seed, grants, drop) use the admin credential.
ensure_app_credential() {
  APP_DB_USER="${T_DB_NAME}_app"
  APP_DB_PASSWORD="$(kubectl -n "${NS}" get secret fleet-db -o json 2>/dev/null | jq -r --arg u "${APP_DB_USER}" \
    'select((.data.PGUSER // "" | @base64d) == $u) | .data.PGPASSWORD // empty | @base64d' || true)"
  [ -n "${APP_DB_PASSWORD}" ] || APP_DB_PASSWORD="$(openssl rand -hex 24)"
}
apply_db_admin_secret() {
  kubectl -n "${NS}" apply -f - >/dev/null <<YAML
apiVersion: v1
kind: Secret
metadata:
  name: fleet-db-admin
  labels: { demo/token: "${TOKEN}" }
type: Opaque
data:
  PGPASSWORD: $(printf '%s' "${DB_PASSWORD}" | base64 | tr -d '\n')
  APP_PGPASSWORD: $(printf '%s' "${APP_DB_PASSWORD}" | base64 | tr -d '\n')
stringData:
  PGHOST: "${RDS_HOST}"
  PGPORT: "${RDS_PORT}"
  PGUSER: "${DB_USER}"
  PGDATABASE: "${T_DB_NAME}"
  APP_PGUSER: "${APP_DB_USER}"
YAML
}
create_app_role() {
  local script
  script="$(cat <<'EOF'
set -e
psql -d otterworks -v ON_ERROR_STOP=1 -q -v r="$APP_PGUSER" -v p="$APP_PGPASSWORD" -v d="$PGDATABASE" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN', :'r') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'r') \gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'r', :'p') \gexec
SELECT format('GRANT %I TO CURRENT_USER', :'r') WHERE NOT pg_has_role(current_user, :'r', 'MEMBER') \gexec
SELECT format('REVOKE CONNECT ON DATABASE %I FROM PUBLIC', :'d') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'d', :'r') \gexec
SQL
echo "role $APP_PGUSER ready"
EOF
)"
  run_job gf-db-role "postgres:16-alpine" "${script}"
}
grant_app_role() {
  local script
  script="$(cat <<'EOF'
set -e
psql -v ON_ERROR_STOP=1 -q -v r="$APP_PGUSER" <<'SQL'
SELECT format('ALTER SCHEMA public OWNER TO %I', :'r') \gexec
SELECT format('ALTER TABLE public.%I OWNER TO %I', tablename, :'r') FROM pg_tables WHERE schemaname = 'public' \gexec
SQL
echo "public schema owned by $APP_PGUSER"
EOF
)"
  run_job gf-db-grant "postgres:16-alpine" "${script}"
}
drop_app_role() {
  local script
  kubectl -n "${NS}" get secret fleet-db-admin >/dev/null 2>&1 || return 0
  kubectl -n "${NS}" scale deploy --all --replicas=0 >/dev/null
  script="$(cat <<'EOF'
set -e
psql -d otterworks -v ON_ERROR_STOP=1 -q -v r="$APP_PGUSER" -v d="$PGDATABASE" <<'SQL'
SELECT format('DROP DATABASE IF EXISTS %I WITH (FORCE)', :'d') \gexec
SELECT format('DROP ROLE IF EXISTS %I', :'r') \gexec
SQL
echo "dropped $PGDATABASE and $APP_PGUSER"
EOF
)"
  run_job gf-db-drop "postgres:16-alpine" "${script}"
}

# After tenant: one fleet-service per country profile (uk, de), each on its own
# schema of the after database, behind the one host:
#   /                  fleet-web
#   /api/uk/...        fleet-service-uk (rewritten to /api/...)
#   /api/de/...        fleet-service-de
#   /api/...           fleet-service-de, or fleet-service-uk with X-Fleet-Country: uk
AFTER_COUNTRIES=(uk de)
up_after() {
  set_tenant after
  local svc_dir="${GF_ROOT}/fleet-service" web_dir="${GF_ROOT}/frontend/fleet" c
  [ -f "${svc_dir}/Dockerfile" ] || { err "${svc_dir#"${REPO_ROOT}"/}/Dockerfile not found on $(git -C "${REPO_ROOT}" rev-parse --abbrev-ref HEAD)"; exit 1; }
  [ -f "${web_dir}/Dockerfile" ] || { err "${web_dir#"${REPO_ROOT}"/}/Dockerfile not found on $(git -C "${REPO_ROOT}" rev-parse --abbrev-ref HEAD)"; exit 1; }
  log "Tenant ${TENANT_ID} (${NS}), token ${TOKEN}, expires ${EXPIRES_AT}"
  load_db_admin; ecr_login
  step "build+push gf-fleet-service" build_push gf-fleet-service "${svc_dir}" "${svc_dir}/Dockerfile" \
    --build-arg "MAVEN_MIRROR=${MAVEN_MIRROR}"
  step "build+push gf-fleet-web" build_push gf-fleet-web "${web_dir}" "${web_dir}/Dockerfile"
  step "build+push gf-seed" build_push gf-seed "${GF_ROOT}" "${HERE}/seed.Dockerfile"
  step "namespace+quota+netpol" apply_namespace
  step "control-table item" put_control_item
  step "db secret" apply_db_secret
  step "create database" create_database
  step "load legacy seed" load_after_seed
  step "deploy services+web" deploy_after_apps
  step "ingress" apply_after_ingress
  step "rollout" wait_rollouts fleet-service-uk fleet-service-de fleet-web
  step "fill country schemas" fill_after_schemas
  step "https ${WEB_HOST}/" wait_https "https://${WEB_HOST}/"
  for c in "${AFTER_COUNTRIES[@]}"; do
    step "https /api/${c}/v1/profile" wait_https "https://${WEB_HOST}/api/${c}/v1/profile"
  done
  print_timings "${TOKEN}-up"
  log "App: https://${WEB_HOST}/  (API: /api/uk, /api/de)"
}
# Pin pods to the pushed digest so a rebuilt image under the same token tag rolls out.
image_ref() {
  local ref="${ECR_REGISTRY}/${ECR_PREFIX}/$1:${TOKEN}" digest
  digest="$(docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "${ref}" 2>/dev/null \
    | grep -m1 "^${ECR_REGISTRY}/${ECR_PREFIX}/$1@" || true)"
  echo "${digest:-${ref}}"
}
deploy_after_apps() {
  local c
  for c in "${AFTER_COUNTRIES[@]}"; do deploy_fleet_service "${c}"; done
  deploy_app fleet-web "$(image_ref gf-fleet-web)" 8080 / 10m 32Mi 200m 128Mi
}

# deploy_fleet_service <country>: the profile and schema are per pod; the
# credential comes from fleet-db like every other app in the tenant.
deploy_fleet_service() {
  local c="$1" name="fleet-service-$1"
  local url="jdbc:postgresql://${RDS_HOST}:${RDS_PORT}/${T_DB_NAME}?sslmode=prefer&currentSchema=${c}"
  kubectl -n "${NS}" apply -f - >/dev/null <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${name}
  labels: { app: ${name}, demo/token: "${TOKEN}", fleet/country: ${c} }
spec:
  replicas: 1
  selector: { matchLabels: { app: ${name} } }
  template:
    metadata:
      labels: { app: ${name}, demo/token: "${TOKEN}", fleet/country: ${c} }
    spec:
      securityContext: { runAsNonRoot: true }
      containers:
        - name: fleet-service
          image: $(image_ref gf-fleet-service)
          imagePullPolicy: Always
          ports: [ { containerPort: 8080 } ]
          envFrom: [ { secretRef: { name: fleet-db } } ]
          env:
            - { name: SPRING_PROFILES_ACTIVE, value: "${c}" }
            - { name: DB_URL, value: "${url}" }
            - { name: SPRING_DATASOURCE_URL, value: "${url}" }
            - { name: SPRING_FLYWAY_SCHEMAS, value: "${c}" }
            - { name: SPRING_FLYWAY_DEFAULT_SCHEMA, value: "${c}" }
          readinessProbe: { httpGet: { path: /actuator/health, port: 8080 }, initialDelaySeconds: 15, periodSeconds: 5, failureThreshold: 60 }
          livenessProbe: { httpGet: { path: /actuator/health, port: 8080 }, initialDelaySeconds: 180, periodSeconds: 20 }
          resources:
            requests: { cpu: 100m, memory: 512Mi }
            limits: { cpu: "1", memory: 1Gi }
---
apiVersion: v1
kind: Service
metadata:
  name: ${name}
  labels: { app: ${name}, demo/token: "${TOKEN}" }
spec:
  type: ClusterIP
  selector: { app: ${name} }
  ports: [ { port: 80, targetPort: 8080 } ]
YAML
}

apply_after_ingress() {
  kubectl -n "${NS}" apply -f - >/dev/null <<YAML
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tenant-ingress
  labels: { demo/token: "${TOKEN}" }
spec:
  ingressClassName: nginx
  rules:
    - host: ${WEB_HOST}
      http:
        paths:
          - { path: /, pathType: Prefix, backend: { service: { name: fleet-web, port: { number: 80 } } } }
          - { path: /api, pathType: Prefix, backend: { service: { name: fleet-service-de, port: { number: 80 } } } }
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tenant-api-country
  labels: { demo/token: "${TOKEN}" }
  annotations:
    nginx.ingress.kubernetes.io/use-regex: "true"
    nginx.ingress.kubernetes.io/rewrite-target: /api/\$2
spec:
  ingressClassName: nginx
  rules:
    - host: ${WEB_HOST}
      http:
        paths:
          - { path: "/api/uk(/|$)(.*)", pathType: ImplementationSpecific, backend: { service: { name: fleet-service-uk, port: { number: 80 } } } }
          - { path: "/api/de(/|$)(.*)", pathType: ImplementationSpecific, backend: { service: { name: fleet-service-de, port: { number: 80 } } } }
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tenant-api-header
  labels: { demo/token: "${TOKEN}" }
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-by-header: X-Fleet-Country
    nginx.ingress.kubernetes.io/canary-by-header-value: uk
spec:
  ingressClassName: nginx
  rules:
    - host: ${WEB_HOST}
      http:
        paths:
          - { path: /api, pathType: Prefix, backend: { service: { name: fleet-service-uk-header, port: { number: 80 } } } }
---
# ingress-nginx turns a canary's service into an alternative backend everywhere,
# so the header route gets its own Service over the same pods.
apiVersion: v1
kind: Service
metadata:
  name: fleet-service-uk-header
  labels: { app: fleet-service-uk, demo/token: "${TOKEN}" }
spec:
  type: ClusterIP
  selector: { app: fleet-service-uk }
  ports: [ { port: 80, targetPort: 8080 } ]
YAML
}

# The before tenant's seed goes into schema legacy (JSF portal, de) and
# legacy_uk (mainframe unloads); fleet-service owns schemas uk and de through
# Flyway, and fill_after_schemas copies the seed people into them once the
# migrations have run.
load_after_seed() {
  local script
  script="$(cat <<'EOF'
set -e
psql -v ON_ERROR_STOP=1 -q -v r="$APP_PGUSER" <<'SQL'
DROP SCHEMA IF EXISTS legacy, legacy_uk, uk, de CASCADE;
SELECT format('CREATE SCHEMA %I AUTHORIZATION %I', s, :'r') FROM unnest(ARRAY['legacy', 'legacy_uk', 'uk', 'de']) AS s \gexec
SQL
PGOPTIONS='-c search_path=legacy' psql -v ON_ERROR_STOP=1 -q -f /seed/001_schema.sql
PGOPTIONS='-c search_path=legacy' psql -v ON_ERROR_STOP=1 -q -f /seed/002_seed.sql >/dev/null
psql -v ON_ERROR_STOP=1 -q -f /seed/uk_unload.sql >/dev/null
psql -v ON_ERROR_STOP=1 -q -v r="$APP_PGUSER" <<'SQL'
SELECT format('ALTER TABLE %I.%I OWNER TO %I', schemaname, tablename, :'r') FROM pg_tables WHERE schemaname IN ('legacy', 'legacy_uk') \gexec
SQL
psql -tAc "SELECT 'seeded ' || (SELECT count(*) FROM legacy.employee) || ' de and ' || (SELECT count(*) FROM legacy_uk.employee) || ' uk employee records'"
EOF
)"
  run_job gf-seed "${ECR_REGISTRY}/${ECR_PREFIX}/gf-seed:${TOKEN}" "${script}"
}
fill_after_schemas() {
  run_job gf-fill "${ECR_REGISTRY}/${ECR_PREFIX}/gf-seed:${TOKEN}" "psql -q -tA -f /seed/after-seed.sql"
}

reset_all() {
  local side found=0 t0
  t0="$(date +%s)"
  load_db_admin
  for side in before after; do
    set_tenant "${side}"
    kubectl get ns "${NS}" >/dev/null 2>&1 || { warn "${NS} not deployed; skipping"; continue; }
    found=$((found + 1))
    step "${TENANT_ID}: db secret" apply_db_secret
    step "${TENANT_ID}: app role" create_app_role
    if [ "${side}" = after ]; then
      step "${TENANT_ID}: load legacy seed" load_after_seed
      step "${TENANT_ID}: restart" restart_all
      step "${TENANT_ID}: fill country schemas" fill_after_schemas
    else
      step "${TENANT_ID}: load seed" load_seed
      step "${TENANT_ID}: restart" restart_all
    fi
  done
  [ "${found}" -gt 0 ] || { err "no ${RUN} tenants found"; exit 1; }
  print_timings "${RUN}-reset"
  log "Reset took $(( $(date +%s) - t0 ))s"
}
restart_all() {
  kubectl -n "${NS}" rollout restart deploy >/dev/null
  local deploys
  read -r -a deploys <<< "$(kubectl -n "${NS}" get deploy -o jsonpath='{.items[*].metadata.name}')"
  wait_rollouts "${deploys[@]}"
}

down_run() {
  local side rc=0
  load_db_admin
  for side in before after; do
    set_tenant "${side}"
    log "Tearing down ${TENANT_ID} (token ${TOKEN})"
    kubectl get ns "${NS}" >/dev/null 2>&1 && { drop_app_role || rc=1; }
    "${REPO_ROOT}/scripts/teardown-tenant.sh" "${TENANT_ID}" --token "${TOKEN}" \
      --host "${WEB_HOST}" --host "${SRC_HOST}" || rc=1
  done
  [ "${rc}" -eq 0 ] && log "Run ${RUN} is gone." || err "Run ${RUN} left residue (see above)."
  return "${rc}"
}

case "${CMD}" in
  up)
    case "${SIDE}" in
      before) up_before ;;
      after)  up_after ;;
      *) err "up needs before or after"; exit 1 ;;
    esac ;;
  reset) reset_all ;;
  down)  down_run ;;
  check)
    load_db_admin
    if [[ "${TOKEN}" =~ ^([a-z0-9-]+)-(before|after)$ ]]; then RUN="${BASH_REMATCH[1]}"; set_tenant "${BASH_REMATCH[2]}"; else TENANT_ID="${TOKEN}"; WEB_HOST=""; SRC_HOST=""; fi
    TOKEN_DB_NAMES="${T_DB_NAME:-}" exec "${REPO_ROOT}/scripts/teardown-tenant.sh" "${TENANT_ID}" --token "${TOKEN}" \
      ${WEB_HOST:+--host "${WEB_HOST}"} ${SRC_HOST:+--host "${SRC_HOST}"} --verify-only ;;
esac
