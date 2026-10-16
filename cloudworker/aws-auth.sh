#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 add|remove <observer-role-arn> <builder-role-arn>" >&2
  exit 2
}

[ "$#" -eq 3 ] || usage
action="$1"
observer_arn="$2"
builder_arn="$3"
case "$action" in add | remove) ;; *) usage ;; esac
for arn in "$observer_arn" "$builder_arn"; do
  [[ "$arn" =~ ^arn:aws[a-z-]*:iam::[0-9]{12}:role/.+$ ]] || {
    echo "not an IAM role ARN: $arn" >&2
    exit 2
  }
done

current="$(kubectl -n kube-system get configmap aws-auth -o json)"

merge_python() {
  CW_ACTION="$action" CW_OBSERVER="$observer_arn" CW_BUILDER="$builder_arn" python3 -c '
import json, os, sys
import yaml

cm = json.load(sys.stdin)
data = cm.setdefault("data", {})
roles = yaml.safe_load(data.get("mapRoles") or "[]") or []
ours = {
    os.environ["CW_OBSERVER"]: "devin-cw-observer",
    os.environ["CW_BUILDER"]: "devin-cw-builder",
}
roles = [r for r in roles if r.get("rolearn") not in ours]
if os.environ["CW_ACTION"] == "add":
    for arn, name in ours.items():
        roles.append({"rolearn": arn, "username": name + ":{{SessionName}}", "groups": [name]})
data["mapRoles"] = yaml.safe_dump(roles, default_flow_style=False, sort_keys=False)
json.dump(cm, sys.stdout)
'
}

merge_yq() {
  CW_ACTION="$action" CW_OBSERVER="$observer_arn" CW_BUILDER="$builder_arn" yq -o=json '
    .data.mapRoles = (
      (.data.mapRoles // "[]" | from_yaml // [])
      | map(select(.rolearn != strenv(CW_OBSERVER) and .rolearn != strenv(CW_BUILDER)))
      | . + (
          select(strenv(CW_ACTION) == "add")
          | [
              {"rolearn": strenv(CW_OBSERVER), "username": "devin-cw-observer:{{SessionName}}", "groups": ["devin-cw-observer"]},
              {"rolearn": strenv(CW_BUILDER), "username": "devin-cw-builder:{{SessionName}}", "groups": ["devin-cw-builder"]}
            ]
          // []
        )
      | to_yaml
    )'
}

if command -v python3 >/dev/null 2>&1 && python3 -c 'import yaml' 2>/dev/null; then
  updated="$(merge_python <<<"$current")"
elif command -v yq >/dev/null 2>&1; then
  updated="$(merge_yq <<<"$current")"
else
  echo "needs python3 with PyYAML, or yq" >&2
  exit 1
fi

if [ "${CW_DRY_RUN:-0}" = "1" ]; then
  echo "dry run: kubectl -n kube-system replace configmap aws-auth with mapRoles:"
  python3 -c 'import json, sys; print(json.load(sys.stdin)["data"]["mapRoles"])' <<<"$updated" 2>/dev/null || echo "$updated"
  exit 0
fi

kubectl replace -f - <<<"$updated" >/dev/null
echo "aws-auth: $action devin-cw-observer and devin-cw-builder mapRoles entries"
