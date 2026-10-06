#!/usr/bin/env bash
# Runs scripts/install-log-shipping.sh against stub kubectl/helm/aws and checks
# that the shared ingress-nginx release is upgraded in place at its deployed
# chart version, never to whatever the local repo cache has as latest.
#   bash infrastructure/helm/aws-for-fluent-bit/tests/test_install_log_shipping.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
STUB="$(mktemp -d)"; trap 'rm -rf "${STUB}"' EXIT
export CALLS="${STUB}/calls" RELEASES="${STUB}/releases"

cat > "${STUB}/helm" <<'STUB_EOF'
#!/usr/bin/env bash
echo "helm $*" >> "${CALLS}"
if [ "$1" = list ]; then cat "${RELEASES}"; fi
STUB_EOF
cat > "${STUB}/kubectl" <<'STUB_EOF'
#!/usr/bin/env bash
echo "kubectl $*" >> "${CALLS}"
STUB_EOF
cat > "${STUB}/aws" <<'STUB_EOF'
#!/usr/bin/env bash
echo "arn:aws:iam::000000000000:role/otterworks-fluent-bit-dev"
STUB_EOF
chmod +x "${STUB}"/helm "${STUB}"/kubectl "${STUB}"/aws
export PATH="${STUB}:${PATH}"

fail() { echo "FAIL: $*" >&2; exit 1; }

echo '[{"name":"ingress-nginx","namespace":"ingress-nginx","revision":"3","status":"deployed","chart":"ingress-nginx-4.11.3","app_version":"1.11.3"}]' > "${RELEASES}"
: > "${CALLS}"
"${REPO_ROOT}/scripts/install-log-shipping.sh" >/dev/null 2>&1 || fail "installer exited non-zero"
grep -q '^helm upgrade ingress-nginx ingress-nginx/ingress-nginx .*--version 4.11.3 .*--reuse-values' "${CALLS}" \
  || fail "ingress-nginx upgrade not pinned to deployed chart 4.11.3: $(grep 'upgrade ingress-nginx' "${CALLS}")"
grep -q '^helm upgrade --install aws-for-fluent-bit eks/aws-for-fluent-bit --version 0.2.0 ' "${CALLS}" \
  || fail "fluent-bit chart not pinned"
echo "ok - ingress-nginx upgraded at deployed chart version"

echo '[]' > "${RELEASES}"
: > "${CALLS}"
if "${REPO_ROOT}/scripts/install-log-shipping.sh" >/dev/null 2>&1; then fail "installer succeeded without an ingress-nginx release"; fi
! grep -q '^helm upgrade' "${CALLS}" || fail "helm upgrade ran without an ingress-nginx release"
echo "ok - missing ingress-nginx release stops before any upgrade"
