#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Safety tests for scripts/teardown-cluster.sh.
#
# The teardown may only destroy the cluster once AWS confirms that nothing the
# in-cluster controllers own (load balancers, Karpenter instances) is still
# alive, because after the destroy nothing is left to reclaim them. Every AWS
# lookup that feeds that decision must therefore fail closed. These tests pin
# that, plus the scope of the Terraform destroy itself.
#
# aws, kubectl and terraform are stubbed on PATH; nothing here touches a real
# account or cluster.
# ------------------------------------------------------------------------------
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEARDOWN="${SCRIPT_DIR}/teardown-cluster.sh"
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  ok   - $1"; }
nope() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else nope "$1 (expected '$3', got '$2')"; fi; }

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
STUBS="${WORK}/bin"
mkdir -p "${STUBS}"

# One Classic ELB, tagged to the cluster being torn down. Its tag lookup can be
# made to throttle, or to race with the ELB's deletion (LoadBalancerNotFound).
cat > "${STUBS}/aws" <<'STUB'
#!/usr/bin/env bash
echo "aws $*" >> "${STATE}/aws.log"
case "$*" in
  *"eks update-kubeconfig"*) exit "${KUBECONFIG_RC:-0}" ;;
  *"elb describe-load-balancers"*) printf '%s\n' "${ELB_NAMES:-}" ;;
  *"elb describe-tags"*)
    case "${ELB_TAGS_MODE:-ok}" in
      throttle) echo "An error occurred (Throttling) when calling the DescribeTags operation: Rate exceeded" >&2; exit 255 ;;
      notfound) echo "An error occurred (LoadBalancerNotFound) when calling the DescribeTags operation: There is no ACTIVE Load Balancer named 'x'" >&2; exit 254 ;;
      *) printf 'kubernetes.io/cluster/otterworks-dev\towned\n' ;;
    esac ;;
  *"elbv2 describe-load-balancers"*) printf '\n' ;;
  *"ec2 describe-security-groups"*) printf '\n' ;;
  *"ec2 describe-volumes"*) printf '0\n' ;;
  *"ec2 describe-instances"*)
    if [ -e "${STATE}/destroyed" ] && [ "${INSTANCES_AFTER_DESTROY:-ok}" = fail ]; then
      echo "An error occurred (RequestLimitExceeded) when calling the DescribeInstances operation" >&2; exit 255
    fi
    printf '%s\n' "${KARPENTER_INSTANCES:-0}" ;;
esac
exit 0
STUB

cat > "${STUBS}/kubectl" <<'STUB'
#!/usr/bin/env bash
echo "kubectl $*" >> "${STATE}/kubectl.log"
exit 0
STUB

cat > "${STUBS}/terraform" <<'STUB'
#!/usr/bin/env bash
echo "terraform $*" >> "${STATE}/terraform.log"
case "$*" in *" destroy "*) touch "${STATE}/destroyed" ;; esac
exit 0
STUB
chmod +x "${STUBS}"/*

# run [VAR=value ...] -- [teardown args]; sets RC, OUT, DESTROYED, TF_ARGS, KUBECTL_CALLS
run() {
  local state="${WORK}/state.$RANDOM$RANDOM"
  mkdir -p "${state}"
  local envs=()
  while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do envs+=("$1"); shift; done
  [ "${1:-}" = "--" ] && shift
  OUT="$(env PATH="${STUBS}:${PATH}" STATE="${state}" DRAIN_TIMEOUT=0 \
           ELB_NAMES="" ELB_TAGS_MODE=ok KARPENTER_INSTANCES=0 \
           "${envs[@]}" bash "${TEARDOWN}" --yes "$@" 2>&1)"
  RC=$?
  if [ -e "${state}/destroyed" ]; then DESTROYED=yes; else DESTROYED=no; fi
  TF_ARGS="$(grep ' destroy ' "${state}/terraform.log" 2>/dev/null || true)"
  KUBECTL_CALLS=0
  if [ -e "${state}/kubectl.log" ]; then KUBECTL_CALLS="$(wc -l < "${state}/kubectl.log" | tr -d ' ')"; fi
}

echo "teardown-cluster safety"

# A throttled tag lookup on a live, cluster-owned ELB is not "not owned": the
# drain must not be waved through and the cluster must survive.
run ELB_NAMES=k8s-ingress ELB_TAGS_MODE=throttle --
check "does not destroy when an ELB tag lookup fails" "${DESTROYED}" "no"
check "  and exits non-zero" "${RC}" "1"

# The ELB disappearing between list and describe-tags is the drain succeeding.
run ELB_NAMES=k8s-ingress ELB_TAGS_MODE=notfound --
check "treats an ELB deleted mid-inventory as released" "${RC}" "0"
check "  and proceeds to destroy" "${DESTROYED}" "yes"

# Karpenter instances outliving the NodeClaim deletion are terminated only by
# the controller that the destroy is about to remove.
run KARPENTER_INSTANCES=1 --
check "does not destroy while Karpenter instances are still running" "${DESTROYED}" "no"
check "  and exits non-zero" "${RC}" "1"

# The final verification must not report success when it could not look.
run INSTANCES_AFTER_DESTROY=fail --
check "fails the verify step when the instance lookup fails" "${RC}" "1"
case "${OUT}" in *"Teardown complete"*) r=claimed ;; *) r=not-claimed ;; esac
check "  and does not claim a clean teardown" "${r}" "not-claimed"

# Happy path: destroys only the cluster module, never the VPC (which the
# application layer's RDS/ElastiCache still occupy) or the ECR repositories
# (force_delete in dev, so their images would go with them).
run --
check "succeeds when everything drained" "${RC}" "0"
case "${TF_ARGS}" in *"-target=module.eks"*) r=targeted ;; *) r=untargeted ;; esac
check "  and destroys only module.eks" "${r}" "targeted"

# Draining one cluster and then destroying another is the worst outcome.
run EKS_CLUSTER=otterworks-staging --
check "refuses when EKS_CLUSTER differs from the Terraform cluster" "${RC}" "1"
check "  without destroying anything" "${DESTROYED}" "no"
check "  and before touching the cluster" "${KUBECTL_CALLS}" "0"

run EKS_CLUSTER=otterworks-staging -- --skip-terraform
check "allows a drain-only run of another cluster" "${RC}" "0"

# An unreachable cluster cannot drain anything; the teardown still proceeds and
# leaves the stranded resources to infra-sweep.sh, as documented.
run KUBECONFIG_RC=1 --
check "still tears down an unreachable cluster" "${DESTROYED}" "yes"

echo
echo "${PASS} passed, ${FAIL} failed"
[ "${FAIL}" -eq 0 ]
