#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Regression test: the runner never runs code from a participant branch.
#
# The runner Job holds the control plane's privileges, and workshop-<id> /
# demo-<id> branches are attendee-writable. This stages a copy of the bundled
# tree, serves a hostile branch from a local git remote that replaces every
# script the runner sources or executes, and asserts that only the bundled
# copies run -- even with REPO_DIR / REPO_HTTPS_URL / GITHUB_TOKEN set the way
# the old branch-checkout path expected.
#
# aws / deploy-tenant.sh are stubbed; no network, no cloud. Runs anywhere with
# bash, git and jq.
# ------------------------------------------------------------------------------
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENTRYPOINT="${ENTRYPOINT_UNDER_TEST:-${SCRIPT_DIR}/entrypoint.sh}"
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  ok   - $1"; }
nope() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
export HOME="${WORK}/home"; mkdir -p "${HOME}"
export GIT_CONFIG_NOSYSTEM=1
MARK="${WORK}/marks"; mkdir -p "${MARK}"

# ---- a hostile participant branch ----------------------------------------------
SRC="${WORK}/attacker-src"
mkdir -p "${SRC}/demo-platform/lib" "${SRC}/scripts/lib"
for f in scripts/lib/tenant-common.sh demo-platform/lib/control-common.sh; do
  printf 'echo "%s" >> "%s/attacker"\n' "${f}" "${MARK}" > "${SRC}/${f}"
done
for s in deploy-tenant teardown-tenant inject-bug tenant-scale; do
  printf '#!/usr/bin/env bash\necho "%s" >> "%s/attacker"\n' "${s}" "${MARK}" > "${SRC}/scripts/${s}.sh"
  chmod +x "${SRC}/scripts/${s}.sh"
done
git -C "${SRC}" init -q -b workshop-evil
git -C "${SRC}" -c user.name=t -c user.email=t@example.invalid add -A
git -C "${SRC}" -c user.name=t -c user.email=t@example.invalid commit -qm evil
git clone -q --bare "${SRC}" "${WORK}/remote.git"

# ---- aws stub (control-table writes succeed, reads are empty) -------------------
mkdir -p "${WORK}/bin"
printf '#!/bin/sh\necho "{}"\n' > "${WORK}/bin/aws"; chmod +x "${WORK}/bin/aws"

# ---- the image's bundled tree (fresh per op) ----------------------------------
IMAGE="${WORK}/image"
stage_image() {
  rm -rf "${IMAGE}"
  mkdir -p "${IMAGE}/demo-platform/runner" "${IMAGE}/demo-platform/lib" "${IMAGE}/scripts/lib"
  cp "${ENTRYPOINT}" "${IMAGE}/demo-platform/runner/entrypoint.sh"
  cp "${REPO_ROOT}/demo-platform/lib/control-common.sh" "${IMAGE}/demo-platform/lib/"
  cp "${REPO_ROOT}/scripts/lib/tenant-common.sh" "${IMAGE}/scripts/lib/"
  local s
  for s in deploy-tenant teardown-tenant inject-bug tenant-scale; do
    cat > "${IMAGE}/scripts/${s}.sh" <<STUB
#!/usr/bin/env bash
echo "${s}" >> "${MARK}/bundled"
[ -z "\${GITHUB_TOKEN:-}" ] || echo "${s}" >> "${MARK}/token-leaked"
STUB
  done
  chmod +x "${IMAGE}"/scripts/*.sh "${IMAGE}/demo-platform/runner/entrypoint.sh"
  rm -f "${HOME}/.gitconfig"
}

run_op() {
  rm -f "${MARK}"/*
  stage_image
  env -i PATH="${WORK}/bin:${PATH}" HOME="${HOME}" GIT_CONFIG_NOSYSTEM=1 \
    OP="$1" TENANT_ID=evil TENANT_BRANCH="${2:-workshop-evil}" SCENARIO=x \
    DB_PASSWORD=test-only KUBERNETES_SERVICE_HOST=stub \
    REPO_DIR="${IMAGE}" REPO_HTTPS_URL="file://${WORK}/remote.git" GITHUB_TOKEN=test-only \
    bash "${IMAGE}/demo-platform/runner/entrypoint.sh" >"${WORK}/out" 2>&1
}

echo "runner executes only the bundled tree"
for op in deploy teardown inject reset wake; do
  run_op "${op}"; rc=$?
  if [ -s "${MARK}/attacker" ]; then
    nope "OP=${op}: ran participant-branch code ($(tr '\n' ' ' < "${MARK}/attacker"))"
  else
    ok "OP=${op}: no participant-branch code ran"
  fi
  if [ "${rc}" -eq 0 ] && [ -s "${MARK}/bundled" ]; then
    ok "OP=${op}: bundled script ran"
  else
    nope "OP=${op}: bundled script did not run (rc=${rc}): $(tail -3 "${WORK}/out")"
  fi
  if [ -e "${MARK}/token-leaked" ]; then
    nope "OP=${op}: GITHUB_TOKEN reached the tenant script"
  else
    ok "OP=${op}: GITHUB_TOKEN not passed on"
  fi
  if [ -e "${IMAGE}/.git" ]; then nope "OP=${op}: bundled tree was turned into a git checkout"; else ok "OP=${op}: bundled tree left untouched"; fi
  if [ -e "${HOME}/.gitconfig" ]; then nope "OP=${op}: git credentials were configured"; else ok "OP=${op}: no git credentials configured"; fi
done

echo "TENANT_BRANCH is validated"
for bad in '../../etc' '-x' 'a b' 'x;id'; do
  run_op deploy "${bad}"; rc=$?
  if [ "${rc}" -ne 0 ] && [ ! -e "${MARK}/bundled" ]; then ok "rejected '${bad}'"; else nope "accepted '${bad}'"; fi
done

echo
echo "${PASS} passed, ${FAIL} failed"
[ "${FAIL}" -eq 0 ]
