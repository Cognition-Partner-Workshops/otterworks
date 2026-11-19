#!/usr/bin/env bash

verify_tenant_rollouts() {
  local namespace="$1" deployments deployment result failed=0
  local -a rows=()
  if ! deployments="$(kubectl -n "${namespace}" get deployments -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')"; then
    printf 'DEPLOYMENT\tROLLOUT\n-\tLIST FAILED\n'
    return 1
  fi
  while IFS= read -r deployment; do
    [ -n "${deployment}" ] || continue
    case ",${VERIFY_IGNORE:-}," in
      *",${deployment},"*) result=IGNORED ;;
      *)
        if kubectl -n "${namespace}" rollout status "deployment/${deployment}" --timeout="${VERIFY_TIMEOUT:-120s}"; then
          result=READY
        else
          result=FAILED
          failed=1
        fi
        ;;
    esac
    rows+=("${deployment}" "${result}")
  done <<< "${deployments}"
  printf '\n%-28s %s\n' DEPLOYMENT ROLLOUT
  if [ "${#rows[@]}" -eq 0 ]; then
    printf '%-28s %s\n' - 'NO DEPLOYMENTS'
    return 1
  fi
  printf '%-28s %s\n' "${rows[@]}"
  return "${failed}"
}
