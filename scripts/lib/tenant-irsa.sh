#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Per-tenant IRSA roles + data (sourced by deploy-tenant.sh / teardown-tenant.sh)
#
# Tenants never assume the shared otterworks-<svc>-<env> roles: those trust only
# the golden namespace (exact subject, Terraform-owned). Each data-bearing
# service in a tenant instead gets its own role:
#
#   role   /otterworks-tenant/ow-<id>-<svc>, tag otterworks-tenant=<id>
#   trust  StringEquals sub = system:serviceaccount:otterworks-<id>:<svc>
#   policy only s3://<bucket>/tenants/<id>/* and table/otterworks-t-<id>--*
#   bound  otterworks-tenant-boundary-<env> (same scope, via the principal tag)
#
# Services outside TENANT_IRSA_SERVICES get no AWS role at all in a tenant.
# ------------------------------------------------------------------------------

TENANT_IRSA_SERVICES=(file-service notification-service audit-service)
TENANT_ROLE_PATH="/otterworks-tenant/"
TENANT_TAG_KEY="otterworks-tenant"

tenant_role_name()   { printf 'ow-%s-%s' "$1" "$2"; }
tenant_s3_prefix()   { printf 'tenants/%s/' "$1"; }
tenant_table_prefix(){ printf 'otterworks-t-%s--' "$1"; }
# <sid> <shared table name> -> otterworks-t-<sid>--<shared without otterworks->
tenant_table_name()  { printf '%s%s' "$(tenant_table_prefix "$1")" "${2#otterworks-}"; }

tenant_trust_policy() { # <oidc provider arn> <oidc url (no scheme)> <namespace> <svc>
  jq -n --arg arn "$1" --arg url "$2" --arg sub "system:serviceaccount:$3:$4" '{
    Version: "2012-10-17",
    Statement: [{
      Effect: "Allow",
      Principal: { Federated: $arn },
      Action: "sts:AssumeRoleWithWebIdentity",
      Condition: { StringEquals: { ($url+":sub"): $sub, ($url+":aud"): "sts.amazonaws.com" } }
    }]
  }'
}

# <svc> <sid> <region> <account>. Reads S3_FILE_BUCKET / S3_AUDIT_BUCKET and the
# already-tenant-scoped DDB_* table names. Prints nothing for unknown services.
tenant_role_policy() {
  local svc="$1" sid="$2" region="$3" account="$4"
  local tbl="arn:aws:dynamodb:${region}:${account}:table" prefix; prefix="$(tenant_s3_prefix "${sid}")"
  local tables
  case "${svc}" in
    file-service)         tables="${DDB_FILE_META} ${DDB_FOLDERS} ${DDB_VERSIONS} ${DDB_SHARES}" ;;
    notification-service) tables="${DDB_NOTIF}" ;;
    audit-service)        tables="${DDB_AUDIT}" ;;
    *) return 0 ;;
  esac
  # shellcheck disable=SC2086  # word-split the table list
  jq -n --arg svc "${svc}" --arg tbl "${tbl}" --arg prefix "${prefix}" \
    --arg fb "${S3_FILE_BUCKET}" --arg ab "${S3_AUDIT_BUCKET}" \
    --args '$ARGS.positional as $t
      | ([ $t[] | select(. != "") | ($tbl+"/"+.), ($tbl+"/"+.+"/index/*") ]) as $tableArns
      | { Version: "2012-10-17", Statement: (
          if $svc == "file-service" then [
            { Sid: "TenantObjects", Effect: "Allow",
              Action: ["s3:GetObject","s3:PutObject","s3:DeleteObject"],
              Resource: ["arn:aws:s3:::"+$fb+"/"+$prefix+"*"] },
            { Sid: "TenantPrefixList", Effect: "Allow", Action: ["s3:ListBucket"],
              Resource: ["arn:aws:s3:::"+$fb],
              Condition: { StringLike: { "s3:prefix": [$prefix+"*"] } } },
            { Sid: "TenantTables", Effect: "Allow",
              Action: ["dynamodb:GetItem","dynamodb:PutItem","dynamodb:UpdateItem",
                       "dynamodb:DeleteItem","dynamodb:Query","dynamodb:Scan"],
              Resource: $tableArns } ]
          elif $svc == "notification-service" then [
            { Sid: "TenantTables", Effect: "Allow",
              Action: ["dynamodb:GetItem","dynamodb:PutItem","dynamodb:UpdateItem","dynamodb:Query"],
              Resource: $tableArns },
            { Sid: "Email", Effect: "Allow", Action: ["ses:SendEmail","ses:SendRawEmail"], Resource: ["*"] } ]
          else [
            { Sid: "TenantTables", Effect: "Allow",
              Action: ["dynamodb:PutItem","dynamodb:GetItem","dynamodb:Query","dynamodb:BatchWriteItem"],
              Resource: $tableArns },
            { Sid: "TenantArchive", Effect: "Allow", Action: ["s3:PutObject"],
              Resource: ["arn:aws:s3:::"+$ab+"/"+$prefix+"*"] } ]
          end) }' ${tables}
}

# Clone a shared table's key schema + GSIs into the tenant's own table.
ensure_tenant_table() { # <shared table> <tenant table> <sid>
  local shared="$1" target="$2" sid="$3"
  aws dynamodb describe-table --region "${AWS_REGION}" --table-name "${target}" >/dev/null 2>&1 && return 0
  local spec; spec="$(aws dynamodb describe-table --region "${AWS_REGION}" --table-name "${shared}" --output json 2>/dev/null)" \
    || { warn "  shared table ${shared} not found; cannot create ${target}"; return 1; }
  local input; input="$(echo "${spec}" | jq -c --arg n "${target}" --arg k "${TENANT_TAG_KEY}" --arg sid "${sid}" '.Table | {
      TableName: $n,
      AttributeDefinitions: .AttributeDefinitions,
      KeySchema: .KeySchema,
      BillingMode: "PAY_PER_REQUEST",
      SSESpecification: { Enabled: true },
      Tags: [{Key: $k, Value: $sid}, {Key: "Project", Value: "otterworks"}]
    } + (if (.GlobalSecondaryIndexes // []) | length > 0 then
      { GlobalSecondaryIndexes: [.GlobalSecondaryIndexes[] | {IndexName, KeySchema, Projection}] }
    else {} end)')"
  aws dynamodb create-table --region "${AWS_REGION}" --cli-input-json "${input}" >/dev/null \
    && aws dynamodb wait table-exists --region "${AWS_REGION}" --table-name "${target}" \
    && log "  created tenant table ${target}"
}

ensure_tenant_role() { # <svc> <sid> <namespace> <oidc arn> <oidc url> <boundary arn> <account>
  local svc="$1" sid="$2" ns="$3" oidc_arn="$4" oidc_url="$5" boundary="$6" account="$7"
  local role; role="$(tenant_role_name "${sid}" "${svc}")"
  local trust; trust="$(tenant_trust_policy "${oidc_arn}" "${oidc_url}" "${ns}" "${svc}")"
  local policy; policy="$(tenant_role_policy "${svc}" "${sid}" "${AWS_REGION}" "${account}")"
  [ -n "${policy}" ] || return 1
  if aws iam get-role --role-name "${role}" >/dev/null 2>&1; then
    aws iam update-assume-role-policy --role-name "${role}" --policy-document "${trust}" >/dev/null || return 1
  else
    aws iam create-role --path "${TENANT_ROLE_PATH}" --role-name "${role}" \
      --assume-role-policy-document "${trust}" --permissions-boundary "${boundary}" \
      --tags "Key=${TENANT_TAG_KEY},Value=${sid}" "Key=Project,Value=otterworks" >/dev/null || return 1
  fi
  aws iam put-role-policy --role-name "${role}" --policy-name tenant-data \
    --policy-document "${policy}" >/dev/null || return 1
  printf 'arn:aws:iam::%s:role%s%s' "${account}" "${TENANT_ROLE_PATH}" "${role}"
}

delete_tenant_roles() { # <sid>
  local sid="$1" svc role p
  for svc in "${TENANT_IRSA_SERVICES[@]}"; do
    role="$(tenant_role_name "${sid}" "${svc}")"
    aws iam get-role --role-name "${role}" >/dev/null 2>&1 || continue
    for p in $(aws iam list-role-policies --role-name "${role}" --query 'PolicyNames[]' --output text 2>/dev/null); do
      aws iam delete-role-policy --role-name "${role}" --policy-name "${p}" >/dev/null 2>&1 || true
    done
    if aws iam delete-role --role-name "${role}" >/dev/null; then
      log "  deleted IRSA role ${role}"
    else
      warn "  failed to delete IRSA role ${role}"
    fi
  done
}

delete_tenant_tables() { # <sid>
  local prefix; prefix="$(tenant_table_prefix "$1")"
  local t
  for t in $(aws dynamodb list-tables --region "${AWS_REGION}" --output json 2>/dev/null \
      | jq -r --arg p "${prefix}" '.TableNames[]? | select(startswith($p))'); do
    if aws dynamodb delete-table --region "${AWS_REGION}" --table-name "${t}" >/dev/null; then
      log "  deleted tenant table ${t}"
    else
      warn "  failed to delete tenant table ${t}"
    fi
  done
}
