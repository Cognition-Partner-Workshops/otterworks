#!/usr/bin/env bash
# Prove the gate passes a compliant service and fails each broken rule.
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
ex="$here/examples/sample-service"
repo=599083837640.dkr.ecr.us-east-1.amazonaws.com/otterworks/sample-service
fail=0
expect() { # expect <pass|fail> <rule-id or -> <label> <helm args...>
  want="$1"; rule="$2"; label="$3"; shift 3
  out="$("$here/scripts/policy-check.sh" "$ex" "$repo" "$@" 2>&1)"; rc=$?
  if [[ "$want" == pass && $rc -eq 0 ]] || [[ "$want" == fail && $rc -ne 0 && "$out" == *"$rule"* ]]; then
    echo "ok   $label"
  else
    echo "FAIL $label (rc=$rc)"; echo "$out" | sed 's/^/     /'; fail=1
  fi
}
expect pass -        "compliant sample-service"          t1
expect fail PROBE-01 "probes disabled"                    t1 --set probes.enabled=false
expect fail REG-01   "image outside the approved registry" t1 --set image.repository=docker.io/library/nginx
expect fail REG-02   "latest tag"                          latest
expect fail SEC-01   "runAsNonRoot overridden"             t1 --set-json 'securityContext={"runAsUser":0,"runAsGroup":0}' --post-renderer "$here/tests/root-post-renderer.sh"
expect fail SECRET-01 "password as a literal env value"    t1 --set env.DB_PASSWORD=hunter22
expect fail RES-01   "limits removed"                      t1 --set resources.limits=null
expect fail LABEL-01 "label stripped"                      t1 --post-renderer "$here/tests/strip-label-post-renderer.sh"
cp "$ex/Dockerfile" /tmp/Dockerfile.bad
sed -i 's#python:3.12-slim@sha256:[0-9a-f]*$#python:3.12-slim#; s#^USER 10001#USER root#' /tmp/Dockerfile.bad
out="$(conftest test --no-color --parser dockerfile --policy "$here/policy/conftest" --data "$here/base-images.yaml" \
     --namespace platform.dockerfile /tmp/Dockerfile.bad 2>&1)"
if [[ "$out" == *BASE-01* && "$out" == *BASE-02* ]]; then echo "ok   unpinned base and root user"; else echo "FAIL unpinned base"; fail=1; fi
exit $fail
