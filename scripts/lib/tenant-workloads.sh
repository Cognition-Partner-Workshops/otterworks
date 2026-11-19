#!/usr/bin/env bash

TENANT_WORKLOAD_SELECTOR='otterworks.io/scale-with-tenant=true'

tenant_refresh_jobs() {
  local ns="$1" suspend="$2" jobs job
  jobs="$(kubectl -n "${ns}" get cronjobs -l "${TENANT_WORKLOAD_SELECTOR}" -o name)" || return
  for job in ${jobs}; do
    kubectl -n "${ns}" patch "${job}" --type=merge -p "{\"spec\":{\"suspend\":${suspend}}}" || return
  done
}

tenant_scale_workloads() {
  local ns="$1" replicas="$2" sets
  if [ "${replicas}" = 0 ]; then
    tenant_refresh_jobs "${ns}" true || return
  fi
  kubectl -n "${ns}" scale deployment --all --replicas="${replicas}" || return
  sets="$(kubectl -n "${ns}" get statefulsets -l "${TENANT_WORKLOAD_SELECTOR}" -o name)" || return
  if [ -n "${sets}" ]; then
    kubectl -n "${ns}" scale statefulset -l "${TENANT_WORKLOAD_SELECTOR}" --replicas="${replicas}" || return
  fi
  if [ "${replicas}" != 0 ]; then
    tenant_refresh_jobs "${ns}" false || return
  fi
}

tenant_running_workloads() {
  local ns="$1" deployments sets
  deployments="$(kubectl -n "${ns}" get deploy -o jsonpath='{range .items[*]}{.spec.replicas}{"\n"}{end}')" || return
  sets="$(kubectl -n "${ns}" get statefulsets -l "${TENANT_WORKLOAD_SELECTOR}" -o jsonpath='{range .items[*]}{.spec.replicas}{"\n"}{end}')" || return
  printf '%s\n%s\n' "${deployments}" "${sets}" | awk '$1 > 0 { n++ } END { print n + 0 }'
}
