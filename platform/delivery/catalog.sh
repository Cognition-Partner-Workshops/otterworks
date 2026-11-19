#!/usr/bin/env bash

DELIVERY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# dorny/paths-filter accepts JSON. Catalog changes rebuild the whole set so
# registering a service can publish its first image even if its source is unchanged.
delivery_filters() {
  jq -ce '
    map({key: .name, value: [.context + "/**", "platform/delivery/services.json"]})
    | from_entries
    | .deployable = ["services/**", "frontend/**", "infrastructure/helm/**", "scripts/**",
                     "platform/delivery/services.json", "platform/delivery/catalog.sh"]
  ' "${DELIVERY_DIR}/services.json"
}

# No argument means all services. A JSON array selects just those service names.
delivery_matrix() {
  jq -ce --argjson changed "${1-null}" '
    map(select($changed == null or (.name as $name | $changed | index($name) != null))
        | {name, context})
  ' "${DELIVERY_DIR}/services.json"
}

delivery_catalog_load() {
  local rows name context port core jvm
  rows="$(jq -er '
    .[] | [.name, .context, (.port // 0), (.core // false), (.jvm // false)] | @tsv
  ' "${DELIVERY_DIR}/services.json")" || return 1
  declare -ga ALL_SERVICES=() PROFILE_CORE_SERVICES=()
  declare -gA BUILD_CONTEXT=() CONTAINER_PORT=() JVM_SERVICE=()

  while IFS=$'\t' read -r name context port core jvm; do
    ALL_SERVICES+=("$name")
    BUILD_CONTEXT[$name]="$context"
    if [[ "$port" != 0 ]]; then CONTAINER_PORT[$name]="$port"; fi
    if [[ "$core" == true ]]; then PROFILE_CORE_SERVICES+=("$name"); fi
    if [[ "$jvm" == true ]]; then JVM_SERVICE[$name]=1; fi
  done <<< "$rows"
}
