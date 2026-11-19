#!/usr/bin/env bash
set -euo pipefail

source "$(dirname -- "${BASH_SOURCE[0]}")/catalog.sh"
repo_root="$(cd -- "${DELIVERY_DIR}/../.." && pwd)"

jq -e '
  type == "array" and length > 0
  and (map(.name) | length == (unique | length))
  and (map(.context) | length == (unique | length))
  and any(.[]; .core == true)
  and all(.[];
    (keys - ["name", "context", "port", "core", "jvm"] | length == 0)
    and (.name | test("^[a-z][a-z0-9]*(-[a-z0-9]+)*$") and length <= 63)
    and (.name != "changes" and .name != "deployable")
    and (.context | test("^(services|frontend)(/[a-zA-Z0-9_-]+)+$"))
    and (if has("port") then (.port | type == "number" and . == floor and . >= 1 and . <= 65535) else true end)
    and (if has("core") then (.core | type == "boolean") else true end)
    and (if has("jvm") then (.jvm | type == "boolean") else true end))
' "${DELIVERY_DIR}/services.json" >/dev/null || { echo "Invalid delivery catalog" >&2; exit 1; }

delivery_catalog_load
for service in "${ALL_SERVICES[@]}"; do
  [[ -f "${repo_root}/${BUILD_CONTEXT[$service]}/Dockerfile" ]] ||
    { echo "Missing Dockerfile for ${service}" >&2; exit 1; }
  [[ -f "${repo_root}/infrastructure/helm/${service}/Chart.yaml" ]] ||
    { echo "Missing Helm chart for ${service}" >&2; exit 1; }
done

matrix="$(delivery_matrix)"
filters="$(delivery_filters)"
[[ "$(jq -r '.[].name' <<< "$matrix")" == "$(printf '%s\n' "${ALL_SERVICES[@]}")" ]]
[[ "$(delivery_matrix '["deployable"]')" == '[]' ]]
[[ "$(delivery_matrix '["web-app","deployable"]')" == '[{"name":"web-app","context":"frontend/client-app"}]' ]]
jq -e '."web-app" == ["frontend/client-app/**", "platform/delivery/services.json"]
  and (.deployable | index("platform/delivery/services.json") != null)' <<< "$filters" >/dev/null
[[ "${CONTAINER_PORT[auth-service]}" == 8081 && "${JVM_SERVICE[auth-service]}" == 1 ]]
[[ " ${PROFILE_CORE_SERVICES[*]} " != *" admin-service "* ]]
echo "Delivery catalog, build selection, and deploy profiles passed"
